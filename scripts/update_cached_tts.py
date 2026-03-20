"""
Input:
  - text-data of a project:
    {
      data: [
        {text: str, ...}
      ],
      project: dajuan
    }
  - tts_model: TtsModel

Logic:
  1. list online datas
  2. decide the update list:
     - add(gen) list
     - del list
  3. do add on each text
  4. del

! Explain the update-list:
1. data that not exists in server
2. data exists in server, while its audio is corrupted
3. data exists in server, while its tts-model quality is lower than required tts-model
   SO: if server tts-model quality is higher/equal to the required model, we do nothing
"""

import argparse
import asyncio
import json

from fs_pyutils.audio import audio_to_mp3_bytes
from pydantic import BaseModel, ConfigDict

from fs_tts_server.client import cached_tts as cached_tts_client
from fs_tts_server.config import CONF, LOGGER as logger, TTS_MODEL2QUALITY_VALUE
from fs_tts_server.config.data_types import TtsModel
from fs_tts_server.repositories import TtsIdGenFnVersionT, clean_tts_text
from fs_tts_server.tts_provider.factory import TtsProviderFactory


def main():
  parser = argparse.ArgumentParser(description="Update cached tts")
  parser.add_argument(
    "--text_data_file",
    "-t",
    required=True,
    help=(
      "path to text data json file, which should be the full latest data, "
      "or you can set `--disable_del` to only add the increasing data"
    ),
  )
  parser.add_argument(
    "--tts_model",
    "-m",
    required=True,
    choices=TTS_MODEL2QUALITY_VALUE.keys(),
    type=TtsModel,
    help="tts model",
  )
  parser.add_argument("--disable_del", "-dd", help="if set, disable deleting the data that only exists in server")
  args = parser.parse_args()
  latest_datas, project = _load_input_key_data(args.text_data_file, args.tts_model)
  server_datas = _load_server_key_data(project)
  _add_tts(latest_datas, server_datas)
  if not args.disable_del:
    _del_tts(latest_datas, server_datas)
  else:
    logger.info("Disable del, skip del step")


class TtsKeyData(BaseModel):
  model_config = ConfigDict(frozen=True)

  text: str
  project: str
  model: TtsModel
  id_version: TtsIdGenFnVersionT = "v1"


def _load_input_key_data(fpath: str, model: TtsModel) -> tuple[list[TtsKeyData], str]:
  with open(fpath) as f:
    raw_data = json.load(f)
  datas: list[TtsKeyData] = []
  project = raw_data["project"]
  for text_data in raw_data["data"]:
    text = text_data["text"]
    kd = TtsKeyData(text=text, project=project, model=model)
    datas.append(kd)
  return (datas, project)


def _load_server_key_data(project: str) -> list[TtsKeyData]:
  """Here we'll filter out the audio-invalid data"""
  list_datas = asyncio.run(
    cached_tts_client.async_list(base_url=CONF.app_domain, api_key=CONF.auth_apikey, project=project)
  )
  server_data: list[TtsKeyData] = []
  for d in list_datas:
    if not d.is_valid_audio:
      logger.info(f"text=[{d.text}] got invalid audio")
      continue
    d = TtsKeyData(text=d.text, project=project, model=d.tts_model)
    server_data.append(d)
  return server_data


def _add_tts(
  latest_datas: list[TtsKeyData], server_datas: list[TtsKeyData]
) -> tuple[list[TtsKeyData], list[TtsKeyData]]:
  """Return:
  (success-list, fail-list)
  """

  def is_server_tts_model_meet_requirement(server_model: TtsModel, required_model: TtsModel) -> bool:
    s_q = TTS_MODEL2QUALITY_VALUE[server_model]
    r_q = TTS_MODEL2QUALITY_VALUE[required_model]
    return s_q >= r_q

  def _calc_newly_gen_candidates() -> list[TtsKeyData]:
    """
    1. data not exists in server
    2. data exists in server while its audio quality is lower than required tts-model
    """

    def _make_key(d: TtsKeyData) -> tuple[str, str, TtsIdGenFnVersionT]:
      return (d.project, clean_tts_text(d.text), d.id_version)

    latest_key2data = {_make_key(d): d for d in latest_datas}
    server_key2data = {_make_key(d): d for d in server_datas}
    gen_candidates: list[TtsKeyData] = []
    new_cnt = 0
    quality_upgrade_cnt = 0
    for key, data in latest_key2data.items():
      if key not in server_key2data:
        # not exists in server
        gen_candidates.append(data)
        new_cnt += 1
        continue
      # compare model
      server_model = server_key2data[key].model
      if not is_server_tts_model_meet_requirement(server_model=server_model, required_model=data.model):
        gen_candidates.append(data)
        quality_upgrade_cnt += 1
    logger.info(
      f"Newly-Gen Candidates: Total=[{new_cnt + quality_upgrade_cnt}]"
      f", new-cnt=[{new_cnt}], tts-quality-upgrade-cnt=[{quality_upgrade_cnt}]"
    )
    return gen_candidates

  def _batch_gen_and_add(datas: list[TtsKeyData]) -> None:
    if not datas:
      return
    tts_model = datas[0].model
    tts_provider = TtsProviderFactory.get_provider(tts_model)
    if not tts_provider:
      raise Exception(f"No Tts provider for model={tts_model}")

    input_texts = [d.text for d in datas]
    batch_audio_bytes = tts_provider.sync_batch_synthesize(texts=input_texts)
    batch_mp3_audio_bytes = [audio_to_mp3_bytes(ab, sample_rate=24000, bitrate="96k") for ab in batch_audio_bytes]

    project = datas[0].project
    id_version = datas[0].id_version
    for input_text, mp3_audio_bytes in zip(input_texts, batch_mp3_audio_bytes):
      asyncio.run(
        cached_tts_client.async_add(
          base_url=CONF.app_domain,
          api_key=CONF.auth_apikey,
          text=input_text,
          project=project,
          tts_model=tts_model,
          mp3_audio_data=mp3_audio_bytes,
          id_version=id_version,
        )
      )

  newly_candidates = _calc_newly_gen_candidates()
  if not newly_candidates:
    return ([], [])

  TtsProviderFactory.init()  # init the TTS clients
  success_datas: list[TtsKeyData] = []
  fail_datas: list[TtsKeyData] = []
  BZ = 10
  for batch_start_idx in range(0, len(newly_candidates), BZ):
    batch_datas = newly_candidates[batch_start_idx : batch_start_idx + BZ]
    if (batch_start_idx + 1) % 3 == 0:
      logger.info(f"AddTts: Processed {batch_start_idx * BZ} datas")
    try:
      _batch_gen_and_add(batch_datas)
    except Exception as e:
      logger.warning(f"AddTts: failed to add tts for data[{batch_datas}], err={e}")
      fail_datas.extend(batch_datas)
      continue
    success_datas.extend(batch_datas)
  logger.info(f"AddTts: successfully added {len(success_datas)} datas, failed added {len(fail_datas)} datas")
  return (success_datas, fail_datas)


def _del_tts(
  latest_datas: list[TtsKeyData], server_datas: list[TtsKeyData]
) -> tuple[list[TtsKeyData], list[TtsKeyData]]:
  """
  Del datas where data only exists in server side
  """

  def _calc_del_candidates() -> list[TtsKeyData]:
    def _make_key(d: TtsKeyData) -> tuple[str, str, TtsIdGenFnVersionT]:
      return (d.project, clean_tts_text(d.text), d.id_version)

    latest_key2data = {_make_key(d): d for d in latest_datas}
    server_key2data = {_make_key(d): d for d in server_datas}

    del_datas: list[TtsKeyData] = []
    for key, sd in server_key2data.items():
      if key in latest_key2data:
        continue
      del_datas.append(sd)
    logger.info(f"DelTts: need to del {len(del_datas)} datas")
    return del_datas

  def _del1(data: TtsKeyData) -> None:
    asyncio.run(
      cached_tts_client.async_del(
        base_url=CONF.app_domain,
        api_key=CONF.auth_apikey,
        text=data.text,
        project=data.project,
        id_version=data.id_version,
      )
    )

  del_datas = _calc_del_candidates()
  if not del_datas:
    return ([], [])

  success_datas: list[TtsKeyData] = []
  fail_datas: list[TtsKeyData] = []
  for idx, candidate_data in enumerate(del_datas):
    if (idx + 1) % 10 == 0:
      logger.info(f"DelTts: Processed {idx + 1} datas")
    try:
      _del1(candidate_data)
    except Exception as e:
      logger.warning(f"DelTts: failed to del tts for data[{candidate_data}], err={e}")
      fail_datas.append(candidate_data)
      continue
    success_datas.append(candidate_data)
  logger.info(f"DelTts: successfully deleted {len(success_datas)} datas, failed {len(fail_datas)} datas")
  return (success_datas, fail_datas)


if __name__ == "__main__":
  main()

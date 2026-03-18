## Mac env

1. Nginx
   link `/deploy/nginx.dev.conf` to `/opt/homebrew/etc/nginx/servers/tts-server-dev.conf`
   
   `brew services restart nginx`
   `brew services info nginx`

   log is sent to a syslog collector. It has a dummy impl, listening 11514, 
   use `dummy_syslog_receiver.py` to run it, else you can ask ChatGPT to generate one.

   Nginx is listening port `3342`.

   in fact you can ignore the nginx proxy if you are in dev mode. Use this file mainly to test the nginx conf for prod.
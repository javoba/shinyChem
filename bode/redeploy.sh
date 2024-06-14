docker kill bode
docker container prune -f
docker build -t javoba/bode .
docker run -d -p 8050:8080 --restart unless-stopped --name bode javoba/bode

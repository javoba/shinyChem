docker kill grating
docker container prune -f
docker build -t javoba/grating .
docker run -d -p 8056:8080 --restart unless-stopped --name grating javoba/grating

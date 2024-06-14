docker kill lixs
docker container prune -f
docker build -t javoba/lixs .
docker run -d -p 8052:8080 --restart unless-stopped --name lixs javoba/lixs

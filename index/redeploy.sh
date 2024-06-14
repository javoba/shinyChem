docker kill webserver
docker container prune -f
docker build -t javoba/webserver .
docker run -d -p 8048:80 --restart unless-stopped --name webserver javoba/webserver

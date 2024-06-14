docker kill rsm
docker container prune -f
docker build -t javoba/rsm .
docker run -d -p 8060:8080 --restart unless-stopped --name rsm javoba/rsm

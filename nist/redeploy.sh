docker kill nist
docker container prune -f
docker build -t javoba/nist .
docker run -d -p 8053:8080 --restart unless-stopped --name nist javoba/nist

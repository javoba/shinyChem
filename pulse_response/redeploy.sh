docker kill pulse-response
docker container prune -f
docker build -t javoba/pulse-response .
docker run -d -p 8051:8080 --restart unless-stopped --name pulse-response javoba/pulse-response

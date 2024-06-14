docker kill distortion
docker container prune -f
docker build -t javoba/distortion .
docker run -d -p 8055:8080 --restart unless-stopped --name distortion javoba/distortion

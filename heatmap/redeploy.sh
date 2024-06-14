docker kill heatmap
docker container prune -f
docker build -t javoba/heatmap .
docker run -d -p 8059:8080 --restart unless-stopped --name heatmap javoba/heatmap

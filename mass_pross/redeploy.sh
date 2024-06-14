docker kill mass-pross
docker container prune -f
docker build -t grva/mass-pross .
docker run -d -p 8057:8180 --restart unless-stopped --name mass-pross grva/mass-pross

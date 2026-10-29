<h2>Deploy Steps</h2>

<h3>Build Docker Images</h3>

```
docker build -t registry.thiran360ai.com/codingboss/api-codingboss -f dockerFile-codingboss-api .
```
<h3>Push To Registry</h3>

```
docker push registry.thiran360ai.com/codingboss/api-codingboss
```
<h3>SSH To Server</h3>

```
ssh sadmin@192.168.1.120
```

<h3>Redeploy K8s Deployment</h3>

```
kubectl rollout restart deployment api-codingboss
```
<h3>Checking the Deployment</h3>

```
kubectl get pods 
```

<p>
It will list the running pods. Check for the pods name api-codingboss-* and its age
</p>


<h3>Trouble shoot Docker Build</h3>

<p>exec /app/entrypoint.sh: no such file or directory</p>

```
git config --global core.autocrlf input
```
```
git rm --cached -r .
```
```
git reset --hard
```

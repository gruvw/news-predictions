from impresso import connect
client = connect(public_api_url="https://dev.impresso-project.ch/public-api/v1")

results = client.search.find("moon landing", limit=2)
print(results)
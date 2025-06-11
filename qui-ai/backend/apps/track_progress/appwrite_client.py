import os
os.environ["CURL_CA_BUNDLE"] = ""



# client = Client()
# client.set_endpoint(os.getenv("APPWRITE_ENDPOINT"))
# client.set_project(os.getenv("APPWRITE_PROJECT_ID"))
# client.set_key(os.getenv("APPWRITE_API_KEY"))

# databases = Databases(client)

from appwrite.client import Client
from appwrite.services.databases import Databases
import os

client = Client()
client.set_endpoint(os.getenv("APPWRITE_ENDPOINT")) \
      .set_project(os.getenv("APPWRITE_PROJECT_ID")) \
      .set_key(os.getenv("APPWRITE_API_KEY"))

databases = Databases(client)

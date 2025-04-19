from dotenv import load_dotenv
from lib.logging import log
import openai
import os

# Load variables from .env file
load_dotenv()

LOG_FILE = "chat_history.log"
WEBPAGE_ACTION_CACHE_FILE_PATH="webpage_action_cache.json"


# Access your keys
config = {
    "openai_api_key": os.getenv("OPENAI_AZURE_API_KEY"),
    "openai_api_version": os.getenv("OPENAI_AZURE_API_VERSION"),
    "openai_azure_deployment": os.getenv("OPENAI_AZURE_DEPLOYMENT"),
    "openai_azure_endpoint": os.getenv("OPENAI_AZURE_ENDPOINT"),
}

openai = openai.AzureOpenAI(
  api_key = config["openai_api_key"],
  api_version = config["openai_api_version"],
  azure_endpoint = config["openai_azure_endpoint"],
  azure_deployment= config["openai_azure_deployment"]
)

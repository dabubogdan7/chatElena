from dotenv import load_dotenv
import os

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
FACEBOOK_PAGE_ACCESS_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")
FACEBOOK_VERIFY_TOKEN = os.getenv("FACEBOOK_VERIFY_TOKEN")
FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET")

BUSINESS_NAME = os.getenv("BUSINESS_NAME", "Firma Noastra")
BUSINESS_PRODUCTS = os.getenv("BUSINESS_PRODUCTS", "produse")
HUMAN_HANDOFF_KEYWORD = os.getenv("HUMAN_HANDOFF_KEYWORD", "agent")

PORT = int(os.getenv("PORT", 8000))

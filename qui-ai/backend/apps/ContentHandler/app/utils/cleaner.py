from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential

# Set up the Azure client
key = "YOUR_AZURE_TEXT_ANALYTICS_KEY"
endpoint = "YOUR_AZURE_TEXT_ANALYTICS_ENDPOINT"

credential = AzureKeyCredential(key)
client = TextAnalyticsClient(endpoint=endpoint, credential=credential)

def clean_text_azure(text: str) -> str:
    try:
        # Extract key phrases (helpful for cleaning and focusing on relevant content)
        response = client.extract_key_phrases([text])
        key_phrases = response[0].key_phrases
        
        # Clean the text by focusing on the key phrases
        cleaned_text = " ".join(key_phrases)  # You can further process this to format it as needed
        
        return cleaned_text
    
    except Exception as e:
        print(f"Error in text cleaning: {str(e)}")
        return text

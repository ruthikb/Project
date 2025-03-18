import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Set up the Chrome WebDriver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service)

# Open Google Meet or any URL to start with
driver.get('https://meet.google.com/')

try:
    while True:
        # Get the current active tab's URL
        current_url = driver.current_url

        # Check if the current URL is a Google Meet URL
        if 'https://workspace.google.com/products/meet/' in current_url:
            print("This is a Google Meet URL.")
        else:
            print("This is not a Google Meet URL.")
        
        # Wait for 5 seconds before checking again
        time.sleep(5)

except KeyboardInterrupt:
    print("Stopping the continuous URL check.")
    driver.quit()

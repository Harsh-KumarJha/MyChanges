import argparse
from datetime import datetime
import boto3
from base64 import b64decode
import os
import time
from datetime import datetime
import logging
import uuid
import json
import csv
import sys
import tempfile
import platform
from tempfile import mkdtemp
import pypdf
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

import subprocess


class automated_tests:

    def __init__(self, url, username, password, mingle_url, mingle_username, mingle_password, email_list, workingdir):
        self.web_url = url
        self.username = username
        self.password = password
        self.mingle_url = mingle_url
        self.mingle_username = mingle_username
        self.mingle_password = mingle_password
        self.email_list = email_list
        self.workingdir= workingdir
        # self.test_prefix = test_prefix
        self.artifacts_directory = os.path.join(os.getcwd(), f'artifacts')
        os.makedirs(self.artifacts_directory, exist_ok=True)
        self.driver = self.get_driver()
        self.space_created = False
        self.notification_created = False
        self.screenshot_index = 0

    def __del__(self):
        if hasattr(self, 'driver') and self.driver:
            self.driver.quit()

    def get_driver(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        # Additional options for better Lambda compatibility
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-features=TranslateUI')
        chrome_options.add_argument('--disable-ipc-flooding-protection')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--remote-debugging-port=9222')
        
        # Set paths for ChromeDriver and Chrome binary
        driver_path = os.path.join(self.workingdir, 'chromedriver')
        chrome_binary_path = os.path.join(self.workingdir, 'chrome-linux', 'chrome')
        
        # Point Chrome options to the binary location
        chrome_options.binary_location = chrome_binary_path
        
        # Verify both files exist
        if not os.path.exists(driver_path):
            raise FileNotFoundError(f"ChromeDriver binary not found at: {driver_path}")
        
        if not os.path.exists(chrome_binary_path):
            raise FileNotFoundError(f"Chrome binary not found at: {chrome_binary_path}")
        
        # Set permissions for ChromeDriver
        logging.info('Setting permissions for ChromeDriver to 0o777')
        os.chmod(driver_path, 0o777)
        
        # Set permissions for Chrome binary and entire chrome-linux directory
        logging.info('Setting permissions for Chrome binary and chrome-linux directory')
        chrome_dir = os.path.join(self.workingdir, 'chrome-linux')
        if os.path.exists(chrome_dir):
            for root, dirs, files in os.walk(chrome_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    try:
                        os.chmod(file_path, 0o777)
                    except Exception as e:
                        logging.warning(f"Could not set permissions for {file_path}: {e}")
        
        logging.info(f"ChromeDriver path: {driver_path}")
        logging.info(f"Chrome binary path: {chrome_binary_path}")
        
        # Create service and driver
        service = Service(executable_path=driver_path)
        
        try:
            driver = webdriver.Chrome(service=service, options=chrome_options)
            logging.info("Chrome driver initialized successfully")
            return driver
        except Exception as e:
            logging.error(f"Failed to initialize Chrome driver: {e}")
            raise e

    def set_element_text(self, text, element_filter, clear=True):
        wait = WebDriverWait(self.driver, 60)
        element = wait.until(EC.element_to_be_clickable(element_filter))
        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
        if clear:
            element.clear()
        ActionChains(self.driver).move_to_element(element).click(element).send_keys_to_element(element, text).perform()
        return element


    def click_with_retries(self, element_filter, retries=3, wait=15, requires_move=False, refresh_page_on_retry=False):
        wait = WebDriverWait(self.driver, wait)
        for attempt in range(retries):
            try:
                if requires_move:
                    if isinstance(element_filter, WebElement):
                        element = element_filter
                    else:
                        element = wait.until(EC.element_to_be_clickable(element_filter))
                    time.sleep(0.5)
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    ActionChains(self.driver).move_to_element(element).click(element).perform()
                    return element
                else:
                    element = wait.until(EC.element_to_be_clickable(element_filter))
                    time.sleep(0.5)
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    self.driver.execute_script("arguments[0].click();", element)
                    return element

            except Exception as e:
                if attempt < (retries - 1):
                    if refresh_page_on_retry:
                        self.driver.refresh()
                    time.sleep(1)
                    pass
                else:
                    raise

    def is_element_clickable(self, element_filter, timeout=10):
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable(element_filter)
            )
            return True
        except:
            return False

    

    def print_job_details(self, job_type_text, job_element):
        logging.info(f"> {job_type_text}:")
        logging.info(f">   {job_element[0].text}")
        logging.info(f">   {job_element[1].text}")
        logging.info(f">   {job_element[3].text}")
        logging.info(f">   {job_element[4].text}")
        logging.info(f">   {job_element[6].text}")

    def login(self):
        try:
            driver = self.driver
            driver.implicitly_wait(30)
            driver.set_page_load_timeout(90)
            logging.info(f"Loading URL {self.web_url}... ")
            driver.get(self.web_url)
            logging.info("..OK")

            logging.info(F"Logging in as {self.username}... ")
            driver.find_element(By.XPATH, "//*[contains(text(), 'LOGIN')]")
            self.set_element_text(self.username, (By.NAME, "username"), False)
            self.set_element_text(self.password, (By.NAME, "password"), False)
            self.click_with_retries((By.XPATH, '//button[@class="btn submit"]'))
            driver.find_element(By.XPATH, "//*[contains(text(), 'Welcome,')]")
            # self.save_screenshot("login.png")
            logging.info("Login was success")
            logging.info("..OK")
        except Exception as e:
            # self.save_screenshot("login-error.png")
            logging.error("Error - Login Failed")
            raise e

    def login_mingle(self):
        try:
            driver = self.driver
            driver.implicitly_wait(30)
            driver.set_page_load_timeout(90)
            wait = WebDriverWait(driver, 15)
            logging.info(f"Loading MINGLE URL {self.mingle_url}... ")
            driver.get(self.mingle_url)
            logging.info("..OK")

            logging.info(F"Testing MINGLE Login with User {self.mingle_username}... ")
            driver.find_element(By.XPATH, "//*[contains(text(), 'Sign In')]")
            self.set_element_text(self.mingle_username, (By.NAME, "username"), False)
            self.set_element_text(self.mingle_password, (By.NAME, "pass"), False)
            driver.find_element("name", "username").submit()
            self.click_with_retries((By.ID, 'osp-nav-launcher'))
            if not self.is_element_clickable(
                    (By.XPATH, "//ids-layout-flex[@data-osp-id='osp-al-app-item' and .//*[contains(text(),'Birst')]]")):
                self.click_with_retries((By.ID, 'osp-al-app-see-more-btn'))
            self.click_with_retries(
                (By.XPATH, "//ids-layout-flex[@data-osp-id='osp-al-app-item' and .//*[contains(text(),'Birst')]]"))
            driver.switch_to.frame(driver.find_element(By.TAG_NAME, "iframe"))
            driver.find_element(By.XPATH, "//*[contains(text(), 'Welcome,')]")
            # self.save_screenshot("mingle-login.png")
            driver.switch_to.default_content()
            self.click_with_retries((By.ID, 'osp-nav-user-profile'))
            self.click_with_retries((By.ID, 'osp-nav-menu-signout'))
            ## Wait for Mingle logout to complete and validate
            time.sleep(30)
            wait.until(
                EC.visibility_of_element_located((By.XPATH, "//div[normalize-space(text())='Logout Successful']")))
            time.sleep(1)
            logging.info("Login was success")
            logging.info("..OK")
        except Exception as e:
            # self.save_screenshot("mingle-login-error.png")
            logging.error("ERROR - MINGLE Login Failed")
            raise e

    
    def get_version(self):
        try:
            logging.info("Capturing site version... ")
            driver = self.driver
            driver.implicitly_wait(10)
            wait = WebDriverWait(driver, 60)
            wait.until(EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'Welcome,')]")))
            wait.until(
                EC.visibility_of_element_located((By.XPATH, '//home-app-launcher-button[@id="create-space-btn"]')))
            self.click_with_retries((By.XPATH, '//button[@id="global-nav-button"]'))
            wait.until(EC.visibility_of_element_located((By.CLASS_NAME, 'version')))
            version = driver.find_element(By.CLASS_NAME, 'version').text
            # self.save_screenshot("get-site-version.png")
            
            logging.info(f'..OK Version: - {version}')

        except Exception as e:
            # self.save_screenshot("get-site-version-error.png")
            logging.error("ERROR - Get Version Failed")
            raise e


    def execute_tests(self):
        try:
            start_time = time.time()
            id = uuid.uuid4()
            # self.space_created = False
            # self.notification_created = False
            # space_name = f"{self.test_prefix} TEST SPACE - {id}"
            # dashboard_name = f"{self.test_prefix} TEST DASHBOARD - {id}"
            # notification_name = f"{self.test_prefix} TEST NOTIFICATION - {id}"
            # connection_name = f"{self.test_prefix} TEST CONNECTION - {id}"
            logging.info(f"Starting automated tests. ID: {id}")
            if self.mingle_url != 'N/A':
                self.login_mingle()
            self.login()
            self.get_version()
            # self.create_space(space_name)
            # self.create_publish_job(connection_name)
            # self.create_dashboard(dashboard_name)
            # self.validate_pdf_export(dashboard_name)
            # self.send_notification(notification_name, self.email_list)
            # self.verify_publish_results()
            # self.verify_notification_results(notification_name)
            logging.info(f"All tests passed in {round(time.time() - start_time, 2)} seconds.")
            return True
        except Exception as e:
            logging.exception(e)
            return False


def load_credential_from_secrets_manager(aws_secret, region_name):
    logging.info('Fetching credentials from AWS Secrets Manager')
    client = boto3.client('secretsmanager', region_name=region_name)
    response = client.get_secret_value(SecretId=aws_secret)
    secret_string = response['SecretString']
    data = json.loads(secret_string)
    if 'mingle_url' in data:
        return data['url'], data['username'], data['password'], data['mingle_url'], data['mingle_username'], data[
            'mingle_password'], data['email_list']
    else:
        return data['url'], data['username'], data['password'], 'N/A', 'N/A', 'N/A', data['email_list']


def main():
    parser = argparse.ArgumentParser(description='get working directory')
    parser.add_argument('--workingdir', help='Working directory')

    args = parser.parse_args()
    working_dir = args.workingdir

    logging.basicConfig(
        level=logging.INFO,  # Set to DEBUG to capture all levels of logs
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            # logging.FileHandler('artifacts/test.log'),
            logging.StreamHandler()
        ]
    )

    
    secret_name = 'birst/synthetic_monitoring/nextdev_login'
    region_name = 'us-west-1'
    url, username, password, mingle_url, mingle_username, mingle_password, email_list = load_credential_from_secrets_manager(secret_name, region_name)

    logging.info(
        f'Setting up tests with url:{url} username:{username} mingle_url: {mingle_url} mingle_username:{mingle_username} email_list:{email_list}')

    # test_prefix = os.getenv('SITE_NAME') or "AUTOMATED"

    tests = automated_tests(url, username, password, mingle_url, mingle_username, mingle_password, email_list, working_dir
                            # test_prefix.upper()
                            )

    if (tests.execute_tests()):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
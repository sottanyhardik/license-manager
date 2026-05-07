"""
DGFT Ownership Checker Script

This script demonstrates the complete flow for checking license ownership on DGFT portal,
including session management and captcha handling.

Usage:
    python dgft_ownership_checker.py --scrip-number 0310836033 --scrip-date 30/04/2020 --iec 0388143011

Note: This script requires manual captcha solving as DGFT uses visual captcha.
"""

import requests
import argparse
from datetime import datetime


class DGFTOwnershipChecker:
    """Handles DGFT ownership checking with session and captcha management"""

    BASE_URL = "https://www.dgft.gov.in"
    APP_ID = "204000000"

    def __init__(self, proxy=None):
        self.session = requests.Session()
        self.csrf_token = None
        self.proxy = proxy

        # Common headers
        self.headers = {
            'Accept': 'text/html, */*; q=0.01',
            'Accept-Language': 'en-GB,en-US;q=0.9,en;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'DNT': '1',
            'Origin': self.BASE_URL,
            'Priority': 'u=1, i',
            'Referer': f'{self.BASE_URL}/CP/?opt=adnavce-authorisation',
            'Sec-CH-UA': '"Google Chrome";v="145", "Chromium";v="145", "Not A(Brand";v="99"',
            'Sec-CH-UA-Mobile': '?0',
            'Sec-CH-UA-Platform': '"macOS"',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest'
        }

        if proxy:
            self.session.proxies = {
                'http': proxy,
                'https': proxy
            }

    def step1_open_modal(self):
        """Step 1: Open the modal and get initial session"""
        print("Step 1: Opening modal and initializing session...")

        url = f"{self.BASE_URL}/CP/webHP"
        params = {
            'requestType': 'ApplicationRH',
            'actionVal': 'commonModal',
            'screenId': '50001',
            '_csrf': self._get_csrf_token()
        }
        data = {'portal': 'CAS'}

        try:
            response = self.session.post(url, params=params, headers=self.headers, data=data, timeout=30)
            response.raise_for_status()

            print(f"✅ Modal opened successfully (Status: {response.status_code})")
            print(f"   Session ID: {self.session.cookies.get('JSESSIONID', 'Not set')}")
            return True

        except requests.RequestException as e:
            print(f"❌ Failed to open modal: {e}")
            return False

    def step2_load_captcha_form(self):
        """Step 2: Load captcha form"""
        print("\nStep 2: Loading captcha form...")

        url = f"{self.BASE_URL}/CP/webHP"
        params = {
            'requestType': 'ApplicationRH',
            'actionVal': 'commonCaptcha',
            'screenId': '90000512',
            '_csrf': self._get_csrf_token()
        }
        data = {'portal': 'CAS'}

        try:
            response = self.session.post(url, params=params, headers=self.headers, data=data, timeout=30)
            response.raise_for_status()

            print(f"✅ Captcha form loaded (Status: {response.status_code})")
            return True

        except requests.RequestException as e:
            print(f"❌ Failed to load captcha form: {e}")
            return False

    def step3_get_captcha_image(self):
        """Step 3: Get captcha image"""
        print("\nStep 3: Fetching captcha image...")

        import time
        timestamp = int(time.time() * 1000)
        url = f"{self.BASE_URL}/CP/SimpleCaptcha?{timestamp}"

        # Change headers for image request
        image_headers = self.headers.copy()
        image_headers['Accept'] = 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
        image_headers['Sec-Fetch-Dest'] = 'image'
        image_headers['Sec-Fetch-Mode'] = 'no-cors'
        del image_headers['Content-Type']
        del image_headers['X-Requested-With']

        try:
            response = self.session.get(url, headers=image_headers, timeout=30)
            response.raise_for_status()

            # Save captcha image
            captcha_file = f'captcha_{timestamp}.png'
            with open(captcha_file, 'wb') as f:
                f.write(response.content)

            print(f"✅ Captcha image saved to: {captcha_file}")
            print(f"   Please solve the captcha and enter the text when prompted")
            return captcha_file

        except requests.RequestException as e:
            print(f"❌ Failed to fetch captcha: {e}")
            return None

    def step4_check_ownership(self, scrip_number, scrip_issue_date, iec_number, captcha_text=None):
        """
        Step 4: Check ownership details

        Args:
            scrip_number: License/scrip number (e.g., "0310836033")
            scrip_issue_date: Issue date in DD/MM/YYYY format (e.g., "30/04/2020")
            iec_number: IEC number (e.g., "0388143011")
            captcha_text: Solved captcha text (if required)
        """
        print(f"\nStep 4: Checking ownership for {scrip_number}...")

        url = f"{self.BASE_URL}/CP/webHP"
        params = {
            'requestType': 'ApplicationRH',
            'actionVal': 'viewScripOwnership',
            'screenId': '90000549',
            '_csrf': self._get_csrf_token()
        }

        data = {
            'scripNumber': scrip_number,
            'scripIssueDate': scrip_issue_date,
            'iecNumber': iec_number,
            'appId': self.APP_ID
        }

        # Add captcha if provided
        if captcha_text:
            data['captcha'] = captcha_text

        try:
            response = self.session.post(url, params=params, headers=self.headers, data=data, timeout=30)
            response.raise_for_status()

            print(f"✅ Ownership check completed (Status: {response.status_code})")

            # Try to parse JSON response
            try:
                result = response.json()
                return result
            except ValueError:
                # If not JSON, return text
                print("⚠️  Response is not JSON, returning raw text")
                return response.text

        except requests.RequestException as e:
            print(f"❌ Failed to check ownership: {e}")
            return None

    def _get_csrf_token(self):
        """Get CSRF token from cookies or generate a placeholder"""
        # In practice, CSRF token should be extracted from the page or cookies
        # For now, using a placeholder - this should be extracted from the initial page load
        if not self.csrf_token:
            # Try to extract from cookies or meta tags
            # This is a placeholder - in production, extract from the page
            import uuid
            self.csrf_token = str(uuid.uuid4())
        return self.csrf_token

    def check_ownership_complete_flow(self, scrip_number, scrip_issue_date, iec_number, auto_captcha=False):
        """
        Complete flow to check ownership with all steps

        Args:
            scrip_number: License/scrip number
            scrip_issue_date: Issue date in DD/MM/YYYY format
            iec_number: IEC number
            auto_captcha: If True, try without captcha (may not work)

        Returns:
            dict: Ownership details or None if failed
        """
        print("="*80)
        print("DGFT Ownership Check - Complete Flow")
        print("="*80)

        # Step 1: Open modal
        if not self.step1_open_modal():
            return None

        # Step 2: Load captcha form
        if not self.step2_load_captcha_form():
            return None

        # Step 3: Get captcha (if needed)
        captcha_text = None
        if not auto_captcha:
            captcha_file = self.step3_get_captcha_image()
            if captcha_file:
                captcha_text = input("\nEnter the captcha text: ").strip()

        # Step 4: Check ownership
        result = self.step4_check_ownership(scrip_number, scrip_issue_date, iec_number, captcha_text)

        print("\n" + "="*80)
        print("RESULT:")
        print("="*80)

        if result:
            if isinstance(result, dict):
                import json
                print(json.dumps(result, indent=2))
            else:
                print(result)
        else:
            print("❌ No result obtained")

        print("="*80)

        return result


def main():
    """Main entry point for command-line usage"""
    parser = argparse.ArgumentParser(
        description='Check DGFT license ownership',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python dgft_ownership_checker.py --scrip-number 0310836033 --scrip-date 30/04/2020 --iec 0388143011

  # With proxy
  python dgft_ownership_checker.py --scrip-number 0310836033 --scrip-date 30/04/2020 --iec 0388143011 --proxy http://proxy:8080

  # Auto mode (without captcha - may not work)
  python dgft_ownership_checker.py --scrip-number 0310836033 --scrip-date 30/04/2020 --iec 0388143011 --auto
        """
    )

    parser.add_argument('--scrip-number', required=True, help='Scrip/License number')
    parser.add_argument('--scrip-date', required=True, help='Scrip issue date (DD/MM/YYYY)')
    parser.add_argument('--iec', required=True, help='IEC number')
    parser.add_argument('--proxy', help='Proxy URL (e.g., http://proxy:8080 or socks5://127.0.0.1:1080)')
    parser.add_argument('--auto', action='store_true', help='Try without captcha (may not work)')

    args = parser.parse_args()

    # Validate date format
    try:
        datetime.strptime(args.scrip_date, '%d/%m/%Y')
    except ValueError:
        print(f"❌ Invalid date format. Please use DD/MM/YYYY format (e.g., 30/04/2020)")
        return

    # Create checker and run
    checker = DGFTOwnershipChecker(proxy=args.proxy)
    result = checker.check_ownership_complete_flow(
        args.scrip_number,
        args.scrip_date,
        args.iec,
        auto_captcha=args.auto
    )

    if result:
        print("\n✅ Ownership check completed successfully!")
    else:
        print("\n❌ Ownership check failed!")


if __name__ == '__main__':
    main()

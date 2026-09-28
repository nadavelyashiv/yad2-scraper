import urllib.request
url = "https://www.madlan.co.il/for-rent/%D7%A9%D7%9B%D7%95%D7%A0%D7%94-%D7%94%D7%93%D7%A8-%D7%99%D7%95%D7%A1%D7%A3-%D7%AA%D7%9C-%D7%90%D7%91%D7%99%D7%91-%D7%99%D7%A4%D7%95-%D7%99%D7%A9%D7%A8%D7%90%D7%9C,%D7%A9%D7%9B%D7%95%D7%A0%D7%94-%D7%9E%D7%A2%D7%95%D7%96-%D7%90%D7%91%D7%99%D7%91-%D7%90-%D7%AA%D7%9C-%D7%90%D7%91%D7%99%D7%91-%D7%99%D7%A4%D7%95-%D7%99%D7%A9%D7%A8%D7%90%D7%9C,%D7%A9%D7%9B%D7%95%D7%A0%D7%94-%D7%9E%D7%A2%D7%95%D7%96-%D7%90%D7%91%D7%99%D7%91-%D7%91-%D7%AA%D7%9C-%D7%90%D7%91%D7%99%D7%91-%D7%99%D7%A4%D7%95-%D7%99%D7%A9%D7%A8%D7%90%D7%9C,%D7%A9%D7%9B%D7%95%D7%A0%D7%94-%D7%A0%D7%90%D7%95%D7%AA-%D7%90%D7%A4%D7%A7%D7%94-%D7%90-%D7%AA%D7%9C-%D7%90%D7%91%D7%99%D7%91-%D7%99%D7%A4%D7%95-%D7%99%D7%A9%D7%A8%D7%90%D7%9C,%D7%A9%D7%9B%D7%95%D7%A0%D7%94-%D7%A0%D7%90%D7%95%D7%AA-%D7%90%D7%A4%D7%A7%D7%94-%D7%91-%D7%AA%D7%9C-%D7%90%D7%91%D7%99%D7%91-%D7%99%D7%A4%D7%95-%D7%99%D7%A9%D7%A8%D7%90%D7%9C,%D7%A9%D7%9B%D7%95%D7%A0%D7%94-%D7%A9%D7%99%D7%9B%D7%95%D7%9F-%D7%93%D7%9F-%D7%AA%D7%9C-%D7%90%D7%91%D7%99%D7%91-%D7%99%D7%A4%D7%95-%D7%99%D7%A9%D7%A8%D7%90%D7%9C?bbox=34.81805%2C32.10622%2C34.82615%2C32.12374&filters=_0-11000________70-__0-10000_______search-filter-top-bar&tracking_search_source=map"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req) as r:
        html = r.read().decode('utf-8')
        print(f"Success! Length: {len(html)}")
        print("listed-bulletin" in html)
except Exception as e:
    print(f"Failed: {e}")

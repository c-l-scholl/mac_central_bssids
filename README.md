# central_query_bssid

queries Aruba Central for all BSSIDs and maps them by AP to an outputted CSV. 

## Output results

This script outputs a CSV with basic AP properities (eth_mac, ip_address, name, serial, site_name) as well as a list of bssids by radio. 

## Set up

1. create a venv following the official python docs for your environment and activate it
2. run command: pip install -r requirements.txt to install project requirements
3. modify your "sample_secrets.yaml" file to include your client id, client secret, token and refresh token from the aruba central instance
4. rename the secrets file "secrets.yaml"
5. update the base_url value in "config.yaml" to the respective api gateway of your instance
6. run the script with /path/to/venv/interpreter/python.exe /path/to/script/directory/main.py
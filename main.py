import asyncio
import aiohttp
import time
import aiohttp.http_exceptions
import aiohttp.web
import pandas as pd
import yaml
from pprint import pprint
import pdb
import traceback

def open_yaml(file: str):
    """open and safe load yaml"""
    with open (file = file, mode = "r") as f:
        content = yaml.safe_load(f)
    return content

async def make_request(session: aiohttp.ClientSession, method: str, url: str, uri: str, headers: dict = {}, params: dict = {}):
    """make async request to webserver at specified url"""
    async with session.request(method = method, url = url + uri, headers = headers, params = params, ssl = False) as r:
        if "error" in r.headers.keys():
            raise aiohttp.web.HTTPException(f"Error existed in token response: {r.headers["error_description"]}")
        r.raise_for_status
        return await r.json()

async def batch_make_request(session: aiohttp.ClientSession, sem: asyncio.Semaphore, method: str, url: str, uri: str, headers: dict = {}, params: dict = {}):
    """makes async requests with semaphore. rate_count_per_sec determines sempahore count. funciton fixed at rate/1 sec"""
    async with sem:
       return await make_request(session, method, url, uri, headers, params)

async def request_until_no_pages(method: str, url: str, uri: str, headers: dict = {}, rate_count_per_sec: int = 7, limit: int = 1):
    """requests bss until no pages; requires calculated total in reponse"""
    aps = []
    sem = asyncio.Semaphore(rate_count_per_sec)
    pages = True
    offset_init = 0
    while pages:
        offset_list = [offset for offset in range(offset_init, offset_init+rate_count_per_sec)]
        async with aiohttp.ClientSession() as session:
            tasks = []
            for offset in offset_list:
                parameters = {"limit": limit, #arbitrary limit for testing pagination
                            "offset": offset}
                task = asyncio.create_task(batch_make_request(session, sem, method, url, uri, headers, parameters))
                tasks.append(task)
                #sleep for rate limit
                await asyncio.sleep(1/rate_count_per_sec)
            responses = await asyncio.gather(*tasks)
        for response in responses:
            #if response isn't empty, join to the responses
            if response["aps"] != []:
                aps += response["aps"]
            #else, break for and break while to return output. 
            elif response["aps"] == []:
                pages = False
                break
        #next set of pages
        offset_init += rate_count_per_sec
    return aps    
        
async def main():
    
#time stamp start
    
    start_time = time.time()
    
#get secret and config params
    
    secrets = open_yaml("secrets.yaml")
    config = open_yaml("config.yaml")
    rate_count_per_sec = 7
#setup request information
    
    base_url = config["base_url"]
    refresh_uri = config["refresh_uri"]
    refresh_method = config["refresh_method"]
    bss_uri = config["bss_uri"]
    bss_method = config["bss_method"]
    apinfo_uri = config["apinfo_uri"]
    apinfo_method = config["apinfo_method"]
    
#refresh token
    
    parameters = {"client_id" : secrets["client_id"],
                  "client_secret": secrets["client_secret"],
                  "grant_type": "refresh_token",
                  "refresh_token": secrets["refresh_token"]}

    #bearer token for header auth
    
    headers = {"accept": "application/json",
            "authorization": f"Bearer {secrets["access_token"]}"}
    
    #refresh token request
    
    try:
        async with aiohttp.ClientSession() as session: 
            
            refresh_token_response = await make_request(session = session, method = refresh_method, url = base_url, uri = refresh_uri, headers = headers, params = parameters)
            await asyncio.sleep(1)
            print("token refreshed!")
    except aiohttp.ServerTimeoutError as e:
    # eg, server unresponsive
        raise SystemExit(f"Something went wrong during the refresh and the server didn't repsond {e.__class__}:{e}")
    
    except aiohttp.web.HTTPException as e:
    # eg, url, server and other errors
        raise SystemExit(f"Something went wrong during the refresh with HTTP {e.__class__}:{e}")
    
    except Exception as e: 
    # catch all
        # pdb.set_trace()
        print(traceback.format_exc())
        raise SystemExit(f"Something went wrong during the refresh {e.__class__}:{e}")




    secrets["access_token"] = refresh_token_response["access_token"]
    secrets["refresh_token"] = refresh_token_response["refresh_token"]
    with open(file = "secrets.yaml", mode = "w") as f:
        yaml.safe_dump(secrets, f)
        
    #Reset headers with current token
    headers = {"accept": "application/json",
            "authorization": f"Bearer {secrets["access_token"]}"}


#No concurrency
    
    # parameters = {"calculate_total": "true"}
    
    # try:
        
    #    bss_response = await make_request(session = aiohttp.ClientSession(), method = bss_method, url = base_url, uri = bss_uri, headers = headers, params = parameters)
       
    # except aiohttp.ServerTimeoutError as e:
    # # eg, server unresponsive
    #     raise SystemExit(f"Something went wrong during the refresh and the server didn't repsond {e.__class__}:{e}")
    # except aiohttp.web.HTTPException as e:
    # # eg, url, server and other errors
    #     raise SystemExit(f"Something went wrong during the refresh with HTTP {e.__class__}:{e}")
    # except Exception as e: 
    # # catch all
    #     # pdb.set_trace()
    #     print(traceback.format_exc())
    #     raise SystemExit(f"Something went wrong during the refresh {e.__class__}:{e}")
    
    # pprint(bss_response)


# #With Concurrency
    #limiting put's less load per call, and can improve performance. 
    #central is hard rate limited at 5000 calls per day at 7 per second. 
    aps_bssids = await request_until_no_pages(method = bss_method, url = base_url, uri = bss_uri, rate_count_per_sec = rate_count_per_sec, headers = headers, limit = 25)
    
    #organize aps into a dictionary for outputting to a dataframe eventually.
    prep = {}
    for index, properties in enumerate(aps_bssids):
        #already flat
        ap = properties["serial"]
        prep[ap] = {}
        prep[ap]["eth_mac"] = properties["macaddr"]
        prep[ap]["name"] = properties["name"]
        prep[ap]["serial"] = properties["serial"]
        #normalizing radios
        for radio in properties["radio_bssids"]:
            radio_index = radio["index"]
            prep[ap][f"radio{radio_index}_wireless_mac"] = radio["macaddr"]
            if hasattr(radio["bssids"], "__iter__"): 
                for index, bssid in enumerate(radio["bssids"]):
                    prep[ap][f"radio{radio_index}_bss{index}_mac"] = bssid["macaddr"]
            else: 
                next
    #pprint(prep)

    aps_info = await request_until_no_pages(method = apinfo_method, url = base_url, uri = apinfo_uri, rate_count_per_sec = rate_count_per_sec, headers = headers, limit = 25)
    with asyncio.

    
    
    #timestamp end and return difference for total run time.     
    exec_time = time.time() - start_time
    print(f"time to execute was: {exec_time}")

if __name__ == "__main__":
    #as main is async, it returns a coroutine, you must add it to the event loop and await its return if you want the result. Or more simply, just use the run funciton from asyncio.
   asyncio.run(main())
"""
To productize:
    input variables - api key
    
    
    Functional process:
        Star top level docs for export in Coda
        Generate API key
        Run program and request api key and export disk location
        Start export for all json items with "contentType": "canvas"
        async the api loops to wait for export ready then download
        name files based on coda page title

USER RUN
    pip install jmespath
    pip install asyncio


2025 July
"""
import asyncio
import aiohttp
import requests
import json
import time
import jmespath
import random

###########################
###   USER INFORMATION  ###
###########################
api_Token = ""
###########################
###   USER INFORMATION  ###
###########################

# static variables
headers = {'Authorization': 'Bearer '}
headers['Authorization'] = 'Bearer '+api_Token
async_delay = 0.7
FAILED_EXPORTS = []
FAILED_PAGE = {
  "name": "",
  "uri": ""
}

# Get list of top level spaces that have been starred
def list_workspace():
    uri = 'https://coda.io/apis/v1/docs'
    params = {
    'isStarred': True,
    }
    res1 = requests.get(uri, headers=headers, params=params)
    res = res1.json()

    # filter output to get and list relevant details for selection
    filtquery = "items[?type=='doc'].{id: id, name: name, href: href}"
    filtout = jmespath.search(filtquery, res)
    return filtout

# Handle List API call pagination
def addNextPage(pgLink, res):
  tmp_res = requests.get(pgLink, headers=headers)
  rs_more = tmp_res.json()
  res['items'].extend(rs_more['items'])
  if 'nextPageLink' in rs_more.keys():
    nextPage = tmp_res['nextPageLink']
    del tmp_res['nextPageLink']
    addNextPage(nextPage, tmp_res)

# Get json formatted response of Coda docs
def list_Docs(selURI):
    uri = selURI+"/pages"
    params = {
        'query': 'New',
    }
    res = requests.get(uri, headers=headers, params=params).json()
    if 'nextPageLink' in res.keys():
        nextPage = res['nextPageLink']
        del res['nextPageLink']
        addNextPage(nextPage, res)
    filtquery = "items[?contentType=='canvas'].{id: id, contentType: contentType, name: name, href: href}"
    filtout = jmespath.search(filtquery, res)
    return filtout
    


#
# Async Controller function for threaded export
async def gen_Export(hrefList):
  print("\nWORKING ")
  async with aiohttp.ClientSession() as session:
    export_responses = []
    
    for singleDoc in hrefList:
      uri1 = f"{singleDoc['href']}/export"
      await asyncio.sleep(async_delay) # Rate limit POST calls
      export_responses.append(asyncio.ensure_future(get_Export_URI(session, uri1, singleDoc['name'])))

    export_List = await asyncio.gather(*export_responses)
    return export_List


# Retrieve export status reference links
async def get_Export_URI(session, uri, out_Name):
  #pause to rate limit
  await asyncio.sleep(1/8)
  async with session.post(uri, headers=headers, json=payload) as resp:
    if resp.ok: 
      export_href = await resp.json()
      await monitor_Export(session, export_href['href'], out_Name)
    else:
      FAILED_EXPORTS.append({'name': out_Name,'uri':uri})
      print("\n   EXPORT FAILURE     -----   "+out_Name+"\n")
    return
      

# Monitor export request for completion
async def monitor_Export(session2, uri2, out_Name):
  tst_loop = True
  while tst_loop:
    await asyncio.sleep(random.randint(1, 5))
    async with session2.get(uri2, headers=headers) as resp2:
      dl_href = await resp2.json()
      if 'statusCode' in dl_href:
        if dl_href['statusCode'] == 429:
          print("\n   429   Too Many Requests   ----   "+out_Name+"\n")
          await asyncio.sleep(random.randint(4, 12))
      if 'status' in dl_href:
        if dl_href['status'] == "complete":
          tst_loop = False
          await download_exports(dl_href['downloadLink'], out_Name)
        if dl_href['status'] != "complete": 
          await asyncio.sleep(1)



# Save exported download links to file
# In thoery not API rate limit as direct s3 downloads
async def download_exports(dl_links, out_Name):
  print(".",end='')
  await asyncio.sleep(1/4)
  res_out = requests.get(dl_links)
  #write respones to file
  with open(out_Name+"."+export_Format, 'w', encoding=res_out.encoding) as md_file:
    md_file.write(res_out.text)



"""
#
      MAIN PROGRAM RUNNING SECTION
#
"""

codaSpaces = list_workspace()

print("\n")
print("\n")
#User choose from starred spaces
sel = 0
for space in codaSpaces:
    print(f"Selection: {sel}      Name: {space['name']}")
    sel+=1

userSel = int(input("Enter Number: "))
print(f"You will be exporting pages from {codaSpaces[userSel]['name']}")

outType = int(input("Enter Number for Export Type\n 1: Markdown  (Does NOT Contain Images)\n 2: HTML\n"))
match outType:
    case 1:
        payload = {  'outputFormat': 'markdown',}
        export_Format = 'md'
    case 2:
        payload = {  'outputFormat': 'html',}
        export_Format = 'html'
    case _:
        print("\n INVALID SELECTION \n")


# Run space query to get list of documents
spaceDocs = list_Docs(codaSpaces[userSel]['href'])

# Run document export
asyncio.run(gen_Export(spaceDocs))

print("\n")
print("Export Completed")
print("\n")
# Display and save any errors if there had been some.
# JSON output can be used as download source to rerun if large task
if len(FAILED_EXPORTS):
    print(f"There were {len(FAILED_EXPORTS)} export failures")
    print("\n")
    print("FAILED_EXPORTS")
    #write respones to file
    with open('FAILEDdocList.json', 'w') as json_file:
        json.dump(FAILED_EXPORTS.toList(), json_file)
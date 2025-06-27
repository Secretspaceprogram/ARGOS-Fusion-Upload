import sys
import requests
import json
import csv
import pandas as pd

if len(sys.argv) != 5:
        print(sys.argv[0] + " <Fusion Stack (AMS, AUS)> <Session Token> <Email Address> <ARGOS CSV File>")
        sys.exit()
else:
    fusion_portal = sys.argv[1]
    session_token = sys.argv[2]
    user_email_address = sys.argv[3]
    csv_file_path = sys.argv[4]

# Generate fusion url based off selected portal
if fusion_portal.lower() == "ams":
    fusion_base_url = "https://fusion.trustwave.com"
    customer_ID = 762452
if fusion_portal.lower() == "aus":
    fusion_base_url = "https://fusion.aus.trustwave.com"
    customer_ID = 1



# Use session tokjn to get user ID (need this to get current assigned projects for user)
def get_user_id(session_token, user_email_address):
    find_user_json_string = '{"@twrpc": "1.0", "@types": ["com.trustwave.dna.common.api.UserSearchCriteria", "com.trustwave.dna.common.api.Role", "com.trustwave.paging.PageRequest"], "@data": [{"roles": [{"value": "DNA_ANALYST_GROUP", "@type": 1}, {"value": "DNA_CONSULTANT_GROUP", "@type": 1}, {"value": "DNA_QA_GROUP", "@type": 1}], "customerIds": [%s], "advancedSearchValue": "%s", "@type": 0}, {"pageNumber": 1, "pageSize": 10, "sortField": "userName", "@type": 2}]}' % (customer_ID,user_email_address)
    find_user_json = json.loads(find_user_json_string)
    headers= {"Cookie": "ng-auth.session=" + session_token,
            "X-Tw-Session-Clientid": session_token}
    proxies = {"http":"http://127.0.0.1:8080",
            "https":"http://127.0.0.1:8080"}
    #change to fusion region of choice
    response = requests.post(fusion_base_url + "/dna-controller/json/userController/findUsers", headers=headers, json=find_user_json,verify=False)
    response.raise_for_status()

    response_json = response.json()
    return response_json["@data"]["pageItems"][0]["userId"]

# Get all project assigned to user, then allow them to select which project to upload to
def get_work_items(session_token, user_id):
    get_work_items_string = '{ "@twrpc": "1.0", "@types": ["com.trustwave.dna.mst.api.dto.workitem.WorkItemSearchCriteria","com.trustwave.dna.mst.api.dto.workitem.WorkItemFilter","com.trustwave.dna.mst.api.dto.workitem.SearchableWorkItemProperties","com.trustwave.dna.mst.api.dto.workitem.CompletionState","com.trustwave.dna.mst.api.dto.workitem.SearchableAssignmentProperties","com.trustwave.paging.PageRequest"], "@data": [{"filters":[[{"workItemProperties":{"uuids":[],"spiderLabsRegions":[],"productClasses":[],"productDeliveries":[],"productTypes":[],"productRealms":[],"productPackages":[],"workItemStatuses":[],"workItemTypes":[],"completionStates":[{"value":"INCOMPLETE","@type":3}],"customerIds":[],"@type":2},"assignmentProperties":{"assigneeIds":[],"unassignedTypes":[],"@type":4},"@type":1}],[{"workItemProperties":{"uuids":[],"spiderLabsRegions":[],"productClasses":[],"productDeliveries":[],"productTypes":[],"productRealms":[],"productPackages":[],"workItemStatuses":[],"workItemTypes":[],"completionStates":[],"customerIds":[],"@type":2},"assignmentProperties":{"assigneeIds":[%s],"unassignedTypes":[],"@type":4},"@type":1}]],"@type":0},{"pageNumber":1,"pageSize":200,"sortCaseInsensitive":true,"sortDescending":false,"sortField":"requestedStartDate","@type":5}]}' % user_id
    get_work_items_json = json.loads(get_work_items_string)
    headers= {"Cookie": "ng-auth.session=" + session_token,
            "X-Tw-Session-Clientid": session_token}
    proxies = {"http":"http://127.0.0.1:8080",
            "https":"http://127.0.0.1:8080"}
    response = requests.post(fusion_base_url + "/dna-controller/json/workItemController/getWorkItems", headers=headers, json=get_work_items_json, verify=False)
    response_json = response.json()
    page_items_list = response_json["@data"]["pageItems"]

    print(page_items_list[0])
    print("SELECT PROJECT:\n\n")
    
    count = 0
    for i in page_items_list:
        print(f"[{count}] - " + i["name"])
        count = count + 1

    selection = input("Input Number Of Project For Upload:\n")
    return(page_items_list[int(selection)]["assignments"][0]["workItemId"])


def generate_affected_asset_html(file_path, rule):
    # Load the Excel file
    df = pd.read_csv(file_path)

    # Group by 'Rule' and collect associated 'Resource Name' values
    grouped = df.groupby('Rule')['Resource Name'].apply(list).reset_index()

    # Create the HTML content
    html_content = r"<li class=\"listItem\">Affected Assets:<br></li><ul class=\"UL\">"
    for _, row in grouped.iterrows():
        if row["Rule"] == rule:
            for resource in row['Resource Name']:
                html_content += fr"<li class=\"listItem\">{resource}<br></li>"
                html_content += r"</li></ul"
            return html_content

# Grab all required data from the CSV and upload it to Fusion
def upload_findings(session_token, work_item, csv_file_path):
    data_list = []
    with open(csv_file_path, 'r', encoding='utf-8') as file:
        csv_reader = csv.reader(file)
        header = next(csv_reader)  # Skip header row, if present
        finding_name = ""
        print(finding_name)
        for row in csv_reader:
            if finding_name != row[3]: # only grab one row for each rule
                finding_name = row[3]
                reference_label = "Refernce"
                reference_value = row[12]
                description_row1 = row[9]
                description_row2 = row[10]
                framework_list = row[13].split("Framework Name:")
                description_row3 = ""
                for i in framework_list[1:]:
                    description_row3 += r'''<li class=\"listItem\">%s<br></li>''' % i
                remediation = "edit me!"
                affected_assets = generate_affected_asset_html(csv_file_path, row[3])
                finding_upload_template = r'''{
                    "@twrpc": "1.0",
                    "@types": [
                        "com.trustwave.dna.mst.api.dto.finding.PenTestFinding",
                        "com.trustwave.dna.common.api.constants.Severity",
                        "com.trustwave.dna.common.api.Reference"
                    ],
                    "@data": [
                        {
                            "workItemId":%s,
                            "name": "%s",
                            "severity": {
                                "value": "INFORMATIONAL",
                                "@type": 1
                            },
                            "classification": "Information.ConfigurationChange",
                            "references": [
                                {
                                    "label": "%s",
                                    "value": "%s",
                                    "@type": 2
                                }
                            ],
                            "description": "<p class=\"paragraph\"><ul class=\"UL\"><li class=\"listItem\">%s<br></li><li class=\"listItem\">%s<br></li><li class=\"listItem\">Compliance Controls:<br></li><ul class=\"UL\">%s</li></ul>%s</p>",
                            "remediation": "<p class=\"paragraph\">%s</p>",
                            "@type": 0
                        }
                    ]
                }''' % (work_item, finding_name, reference_label, reference_value, description_row1, description_row2, description_row3, affected_assets, remediation)
                finding_upload_json = json.loads(finding_upload_template, strict=False)
                headers= {"Cookie": "ng-auth.session=" + session_token, "X-Tw-Session-Clientid": session_token}
                proxies = {"http":"http://127.0.0.1:8080","https":"http://127.0.0.1:8080"}
                response = requests.post(fusion_base_url + "/dna-controller/json/penTestFindingController/saveFinding", headers=headers, json=finding_upload_json, verify=False)
                print(response.status_code)
                #assign_asset_to_finding() #not implemented yet
            else:
                continue

            
    
    

if __name__ == "__main__":
    upload_findings(session_token,get_work_items(session_token, get_user_id(session_token,user_email_address)), csv_file_path)









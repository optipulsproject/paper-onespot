#!/usr/bin/python3

# This script is meant to facilitate the creation of a new Gitlab repository for a publication.
# To this end, it
# * forks numapde-template into a new Gitlab repository with a specified name (shortTitle), 
# * assigns the new repository to a Gitlab namespace different from the default numapde/Publications if desired (namespace)
# * creates a new README.md from the template README.md.in by substitution.

# Define the person(s) responsible for maintenance
maintainers = ('Andreas Naumann, Roland Herzog')

# The Gitlab API access token is obtained from the environment variable NUMAPDE_GITLAB_TOKEN.

import requests
import json
import argparse
import sys
import time
import os

# Specify the Gitlab server
gitlabServer = os.environ.get('NUMAPDE_GITLAB_SERVER', None)
if gitlabServer is None:
    print('Please set the NUMAPDE_GITLAB_SERVER variable.')
    sys.exit(1)

# Specify the URL format to access the Gitlab project API
urlFormat = 'https://' + gitlabServer + '/api/v4/projects/%(projectId)d'

# Specify the default name space 
namespace = 'numapde/Publications'

# Set the repository id for the template to be forked
# https://gitlab.hrz.tu-chemnitz.de/numapde/Publications/numapde-template
templateId = 5326 

# Define some status codes according to https://docs.gitlab.com/ee/api/README.html#status-codes
POST_OK = 201
PUT_OK = 200
GET_OK = PUT_OK

# Provide the command line arguments to the parser
epilog = r"""

Examples:
    {scriptName} "ADMM on Riemannian manifolds" "Riemannian-ADMM" 
    {scriptName} "ADMM on Riemannian manifolds" "Riemannian-ADMM" --namespace numapde/Sandbox
    {scriptName} "ADMM on Riemannian manifolds" "Riemannian-ADMM" --namespace numapde/Sandbox --description "I will describe how to apply ADMM on Riemannian manifolds"
    
Maintainers: {maintainers}""".format(scriptName=sys.argv[0], maintainers=maintainers)
parser = argparse.ArgumentParser(description = 'This script forks the numapde Gitlab template repository for a new publication and provides an initial README.md.', epilog =  epilog , formatter_class = argparse.RawTextHelpFormatter)
parser.add_argument('longTitle', metavar = 'longTitle', help = 'long publication title (will go into the project name on Gitlab)')
parser.add_argument('shortTitle', metavar = 'shortTitle', help = 'short publication title (will determine the repository address on Gitlab)')
parser.add_argument('--namespace', metavar = 'namespace', help = 'Gitlab namespace with default %s.' % namespace, nargs = '?', default = namespace)
parser.add_argument('--description', metavar = 'description', help = 'A short project description for the gitlab web interface. The default is an empty description.', nargs = '?', default = '')

args = parser.parse_args()

# Get the API access token from the environment variable NUMAPDE_GITLAB_TOKEN
privateToken = os.environ.get('NUMAPDE_GITLAB_TOKEN', None)
if privateToken is None:
    print('Please set the NUMAPDE_GITLAB_TOKEN variable to your personal Gitlab access token.')
    sys.exit(1)

# Set the long title
longTitle = args.longTitle

# Replace spaces by hyphens in the short title
shortTitle = args.shortTitle
shortTitle = shortTitle.replace(' ','-')

# Set the namespace
namespace = args.namespace

# Update (empty) the project description
newDescription = args.description

# Define the common header for all API operations
headers = {'Private-Token': privateToken} 

# Prepare the fork action URL
url = urlFormat %{'projectId': templateId} + '/fork'

# Assemble the URL payload for the fork request
# 'name' corresponds to 'Project name' in the 'new project' web interface.
# 'path' corresponds to 'Project slug' in the 'new project' web interface.
payload = {'namespace': namespace, 'name': longTitle, 'id': templateId, 'path': shortTitle}
# print(payload)

# Submit the fork request
print('Requesting the Gitlab server to fork %s into %s%s/%s/%s.' % (url,'https://', gitlabServer, namespace,shortTitle))
r = requests.post(url, headers = headers, data = payload)
# print(r.text)
if(r.status_code != POST_OK):
    print('Something went wrong during forking. The status code is %d and the result text is %s.' % (r.status_code, r.text))
    sys.exit(1)

# Extract the project information into a dictionary 
newProject = json.loads(r.text) 
newId = newProject['id'] 
newUrl = urlFormat %{'projectId': newId}


# Allow the Gitlab server to create the project
nWaitMax = 5
nWaitTime = 2
print('Waiting at most %d seconds to allow Gitlab to create the project...' % (nWaitMax*nWaitTime))
# check if the project exists by inspecting its properties
# if the project has a default branch, we assume it is available 
projInfo = requests.get(newUrl, headers = headers)
projInfo = json.loads(projInfo.text)
# we test at most 5 times, afterwards the non-existence is an error
while projInfo['default_branch'] is None and nWaitMax > 0:
    time.sleep(nWaitTime)
    projInfo = requests.get(newUrl, headers = headers)
    projInfo = json.loads(projInfo.text)
    nWaitMax -= 1

if projInfo['default_branch'] is None:
    print('the project creation took a too long time. Please check yourself if a project with your short title exists at %s%s/%s' %('https://', gitlabServer, namespace))
    sys.exit(1)

# Assemble the URL payload for the project description update request
payload = {'id': newId, 'description': newDescription}

# Submit the commit request
rDescription = requests.put(newUrl, headers = headers, data = payload)
# print(rDescription)
if(rDescription.status_code != PUT_OK):
    print('Updating project description failed. The result text is: ' + rDescription.text)
    sys.exit(1)


# Prepare the new README.md
# https://docs.gitlab.com/ee/api/repository_files.html 
# Prepare the URL for the README.md file in the new repository
readmeUrl = newUrl + '/repository/files/README.md'

# Get path to README.md.in, relative to the directory from where the present script is located
readmePath = os.path.dirname(os.path.abspath(__file__)) + '/../README.md.in'
print('Using template %s.' % readmePath)

# Read the template README.md.in
with open(readmePath) as file:
    readme = file.read()

# Get SSH and HTTP URLs to new project
sshURLToRepo = newProject['ssh_url_to_repo']
httpURLToRepo = newProject['http_url_to_repo']

# Prepare the new README.md file by string substitution
readme = readme % {'PUBLICATION_TITLE': longTitle, 'HTTP_URL_TO_REPO': httpURLToRepo, 'SSH_URL_TO_REPO': sshURLToRepo}

# Assemble the URL payload for the README.md commit request
payload = {'file_path': 'README%2Emd', 'branch': 'master', 'content': readme, 'commit_message': '%s auto-generates README.md' % sys.argv[0]}

# Submit the commit request
rReadme = requests.put(readmeUrl, headers = headers, data = payload)
# print(rReadme)
if(rReadme.status_code != PUT_OK):
    print('Commiting README.md failed. The result text is: ' + rReadme.text)
    sys.exit(1)


# Print a success message
print('Clone the new repository using\n  git clone --recurse-submodules %s' % sshURLToRepo)
print('Then update the submodules via\n  bin/numapde-submodules-update.sh')


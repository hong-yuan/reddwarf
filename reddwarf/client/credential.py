'''
Created on Feb 22, 2012

@author: vipul
'''
class SwiftCredential:
    """Credential to access Swift Storage contains
       user, key and authentication endpoint."""
    def __init__(self, user, key, auth):
        self.user = user
        self.key = key
        self.auth = auth



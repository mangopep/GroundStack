# Authorization status

Authorization and tenant isolation are not implemented. No document ownership or collection scope is present in the API. A filter added only in the response layer would be too late; each retrieval and storage operation must enforce scope. Do not host private documents for multiple users with this code.

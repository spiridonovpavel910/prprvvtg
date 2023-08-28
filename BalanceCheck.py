import requests
import json
import os
from concurrent.futures import ThreadPoolExecutor

filename = 'abc.txt'  # insert file to read addresses from
check_mode = "contracts"  # Choose "addresses" or "contracts"

# Using the newer with construct to close the file automatically.
with open(filename) as f:
    data = f.read().splitlines()

# Break down text file in blocks of 20 for multibalance return. Etherscan allows 20 addresses for multibalance check
def chunks(l, n):
    """Yield successive n-sized chunks from l."""
    for i in range(0, len(l), n):
        yield l[i:i + n]

# Function to fetch balance for a chunk of addresses
def fetch_balances(chunk):
    payload = {
        'module': 'account',
        'action': 'balancemulti',
        'address': ','.join(chunk),  # Join addresses into a comma-separated string
        'tag': 'latest',
        'apikey': '3XJWSH2YJIA7ITUJXH7KPGI57Q4TABI9DD'
    }
    r = requests.get('https://api.etherscan.io/api', params=payload)
    return r.json()

# Function to fetch transactions involving contracts for an address
def fetch_contract_transactions(address, target_method_ids):
    payload = {
        'module': 'account',
        'action': 'txlist',
        'address': address,
        'startblock': 0,
        'endblock': 99999999,
        'sort': 'asc',
        'apikey': '3XJWSH2YJIA7ITUJXH7KPGI57Q4TABI9DD'
    }
    r = requests.get('https://api.etherscan.io/api', params=payload)
    transactions = r.json().get('result', [])
    contract_transactions = [
        {
            'hash': tx.get('hash'),
            'methodId': tx.get('input')[:10],  # Extract first 10 characters of input as methodId
            'value': int(tx.get('value', 0)) / 1e18
        }
        for tx in transactions
        if tx.get('to') is not None and tx.get('input') != '0x' and tx.get('input')[:10] in target_method_ids
    ]
    return contract_transactions

# Create a directory for transaction files
transactions_directory = 'transactions'
os.makedirs(transactions_directory, exist_ok=True)

# Break down the addresses into lists of 20 each
Arraysplits = list(chunks(data, 20))

total_balance = 0
outputfile = open('balanceoutput.txt', 'w')  # log balances into a text file
addresses_with_balance = []
all_contract_transactions = []  # To store all contract transactions

# Define the target MethodIds
target_method_ids = [
    '0x66dfbfb4', '0xd7078df6', '0xa40d3060', '0x60806040', '0xb7e8bc99',
    '0xb6569195', '0x60556023', '0xc41a3be8', '0xccc61a26', '0x54f3596b',
    '0x27a3b4c8', '0xd9ffad47', '0xcc5e3163', 'firstDeposit', '0x30491e82',
    '0xb1a1a882', '0xeb672419', '0x0f4d14e9'
]

# Create a ThreadPoolExecutor with a limited number of workers
max_workers = 3  # You can adjust this based on your system's capacity
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = []
    for chunk in Arraysplits:
        future = executor.submit(fetch_balances, chunk)
        futures.append(future)

    for i, future in enumerate(futures):
        try:
            result = future.result()
            print("Processing chunk: ", i + 1, "/", len(Arraysplits))
            for account in result.get('result', []):
                balance = int(account.get('balance', 0))
                tx_count = int(account.get('transactionCount', 0))
                total_balance += balance

                outputfile.write(json.dumps(account) + "\n")

                if balance > 0:
                    address_info = {
                        'address': account.get('account'),
                        'balance': balance / 1e18,  # Convert balance to ETH
                        'transaction_count': tx_count
                    }
                    addresses_with_balance.append(address_info)
                    
                    # Rest of the address-checking code...
                    if check_mode == "addresses":
                        # Fetch address transactions for each address
                        address_transactions = fetch_address_transactions(account.get('account'))
                        if address_transactions:
                            with open(os.path.join(transactions_directory, f"{account.get('account')}_address_transactions.txt"), 'w') as tx_file:
                                tx_file.write(json.dumps(address_transactions, indent=4))

                    # Rest of the contract-checking code...
                    elif check_mode == "contracts":
                        # Fetch contract transactions for each address
                        contract_transactions = fetch_contract_transactions(account.get('account'), target_method_ids)
                        if contract_transactions:
                            all_contract_transactions.extend(contract_transactions)
                            # Save contract transactions in real-time
                            with open(os.path.join(transactions_directory, f"{account.get('account')}_contract_transactions.txt"), 'w') as tx_file:
                                tx_file.write(json.dumps(contract_transactions, indent=4))
        except Exception as e:
            print("Error fetching balances:", e)

outputfile.close()

# Save addresses with balance and transaction count to a separate text file
with open('addresses_with_balance.txt', 'w') as address_file:
    for address_info in addresses_with_balance:
        address_file.write(json.dumps(address_info, indent=4) + "\n")

# Save all contract transactions to a single file
with open(os.path.join(transactions_directory, 'all_contract_transactions.txt'), 'w') as tx_file:
    tx_file.write(json.dumps(all_contract_transactions, indent=4))

print("Total ETH balance: ", total_balance / 1e18)

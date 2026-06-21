# Ethr-DID Resolver


### Ethr-DID Resolver

#### Overview
The Ethr-DID Resolver is a crucial component that enables the resolution of DIDs into their associated attributes and public keys. It interacts with the Ethereum DID Registry to fetch and interpret the data linked to a DID, making it accessible to applications and services.

#### Key Functions
1. **resolve**: Fetches the DID document by querying the Ethereum blockchain for the relevant attributes and public keys.
2. **getPublicKey**: Retrieves the public key associated with a DID for verification purposes.
3. **getService**: Obtains service endpoints linked to a DID, facilitating communication and interaction with other entities.

#### Role in ERC-1056
The resolver component plays a vital role in translating the on-chain DID information into a standardized DID document format. This allows applications to easily retrieve and utilize DID data, ensuring interoperability and usability within the ERC-1056 framework.


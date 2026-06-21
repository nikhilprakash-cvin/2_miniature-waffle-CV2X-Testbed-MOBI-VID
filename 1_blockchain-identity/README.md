
# CVIN-ID Smart Contracts

Welcome to the CVIN-ID Smart Contracts repository. CVIN is part of a Master of Applied Science (MASc) thesis at the University of British Columbia (UBC), conducted within the Electrical and Computer Engineering department and the Blockchain Interdisciplinary Research Cluster. This project is dedicated to developing a robust Self-Sovereign Identity (SSI) system specifically tailored for Connected and Autonomous Vehicles (CAVs) within the greater Internet of Vehicles (IoV) ecosystem. Our aim is to research the security, verifiability, and flexibility and overall performance and capabilities of digital identities and systems that are built on public blockchain through various standards including the W3C, MOBI VID, and different ERC standards that are capanble of functioning as a digital identity or part of a digital identity / SSI system.

## Overview

The Connected Vehicle Identity Network (CVIN) research leverages and investigates a series of Ethereum Improvement Proposals (EIPs) to create a comprehensive comparison, and overview of potential options (as well their benefits, functinoality and limitations) to serve as potential SSI system for CAVs. This system, at a base level ensures that each vehicle maintains a secure and verifiable identity, facilitating secure interactions and transactions within the IoV. <Include the base case / base goal of enabling secure communication with a verified identity here as a distillation of above.>

### Implementations

We have developed six key implementations, each building upon different Ethereum standards to address specific aspects of decentralized identity and asset management.

#### [Implementation I: ERC-721 - Non-Fungible Token Standard](https://github.com/CVIN-ID/CVIN-ID-SCs/tree/main/ERC721)
ERC-721 is the foundational standard for unique digital identities. It employs non-fungible tokens (NFTs) to represent unique vehicle identities, enabling secure and verifiable ownership and history records. This implementation is crucial for managing unique attributes and providing a base for more complex identity systems.

#### [Implementation II: ERC-725 - Proxy Account Standard](https://github.com/CVIN-ID/CVIN-ID-SCs/tree/main/ERC725)
ERC-725 introduces a flexible proxy account mechanism for managing decentralized identities. It enhances key management, data storage, and proxy execution capabilities, making it suitable for more dynamic identity systems. This implementation allows vehicles to interact with various smart contracts securely and flexibly.

#### [Implementation III: ERC-1155 - Multi-Token Standard](https://github.com/CVIN-ID/CVIN-ID-SCs/tree/main/ERC1155)
ERC-1155 introduces a multi-token standard capable of handling both fungible and non-fungible tokens within a single contract. This versatility is crucial for managing various vehicle-related assets, from ownership tokens to service history and payment tokens. It enables efficient batch transfers and comprehensive token management.

#### [Implementation IV: ERC-725x,y - Enhanced Proxy Account Standard](https://github.com/CVIN-ID/CVIN-ID-SCs/tree/main/ERC725xy)
Building upon ERC-725, this enhanced standard offers advanced key and data management features, optimized for CAVs. The ERC-725x,y implementation ensures greater security and flexibility, supporting the broader CVIN thesis by managing complex identity attributes and permissions efficiently.

#### [Implementation V: ERC-1056 - Lightweight Identity Standard](https://github.com/CVIN-ID/CVIN-ID-SCs/tree/main/ERC1056)
ERC-1056 provides a lightweight approach to managing decentralized identities directly on the blockchain. It focuses on simplicity and efficiency, making it ideal for scenarios where minimal overhead is necessary. This implementation is beneficial for quick identity resolution and basic attribute management.

#### [Implementation VI: LSP8 - ~~~~~ ](https://github.com/CVIN-ID/CVIN-ID-SCs/tree/main/LSP8)
~

#### [Implementation VII: ERC-4337 -  ](https://github.com/CVIN-ID/CVIN-ID-SCs/tree/main/LSP8)
~

#### [Implementation VIIi: CVIN Combined Approach -  ](https://github.com/CVIN-ID/CVIN-ID-SCs/tree/main/CVIN-combbined)
~

#### [Implementation VC-I:  ERC-735 - Claim Holder Standard](https://github.com/CVIN-ID/CVIN-ID-SCs/tree/main/ERC735)
ERC-735 focuses on the management of claims and credentials. It allows for the issuance and verification of claims linked to vehicle identities, integrating seamlessly with the SSI system. This implementation is pivotal for handling verified credentials and ensuring the integrity of vehicle data.

## Deep Dive Investigations

Each implementation is meticulously documented, with in-depth investigations into their unique capabilities and integrations. These deep dives highlight the strengths of each standard, ensuring they meet the specific requirements of the CVIN SSI system.

### Key Highlights

- **ERC-721:** Standout for its simplicity and foundational role in managing unique vehicle identities.
- **ERC-725:** Notable for its advanced proxy mechanisms, providing flexible and secure identity management.
- **ERC-735:** Exceptional in its handling of claims and credentials, essential for verified vehicle data.
- **ERC-725x,y:** Enhanced features for key and data management, optimizing identity security and flexibility.
- **ERC-1155:** Versatility in managing multiple token types, from ownership to payments, with efficient batch transfers.
- **ERC-1056:** Lightweight and efficient, ideal for quick identity resolutions and basic attribute management.

## Getting Started

To get started with the CVIN-ID Smart Contracts, follow the instructions provided in each implementation's README. The repository includes detailed guides for installation, deployment, and testing.

1. Clone the repository:
    ```bash
    git clone https://github.com/CVIN-ID/CVIN-ID-SCs.git
    ```
2. Navigate to the desired implementation directory and follow the setup instructions.

## Contributions

We welcome contributions from the community. If you have suggestions or improvements, feel free to open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](https://github.com/CVIN-ID/CVIN-ID-SCs/blob/main/LICENSE) file for details.

# Capstone Project Proposal

## Overview & Goals
The goal of this project is to develop a web-based data visualization platform that provides interactive and customizable data visualizations without requiring users to log into a Tableau server. The platform will allow users to create custom views, explore different data visualizations (such as bar charts, line graphs, box and whisker plots, etc.), and utilize filters and drilldowns for enhanced data analysis. By achieving this goal, I aim to provide an accessible and user-friendly data visualization solution that can benefit my company and improve data analysis processes.

## User Demographics
The target users of the platform will primarily consist of employees within our company and our clients who require data visualization capabilities for analysis and reporting purposes. The demographic will likely include individuals with varying levels of technical expertise and familiarity with data visualization tools. Therefore, the platform should be designed to accommodate users with diverse skill sets and provide a seamless user experience.

## Specifications
For this project, I plan to utilize the Spotify API as a data source to demonstrate the capabilities of the interactive data visualization platform but want to keep this flexible in order to connect to other data sources in the future. The Spotify API offers a wide range of data related to music, including user playlists, song attributes, artist information, and user listening history. By leveraging this API, we can showcase various visualizations and explore meaningful insights within the music domain. API [here](https://api.spotify.com/v1)

## Approach

### Database Schema
You can find the database schema [here](https://dbdiagram.io/d/645d8cebdca9fb07c4f0f1e8).

### API Challenges
Potential challenges with the selected API may include rate limitations, data access restrictions, and data quality concerns. Thorough research and testing will be conducted to understand the API's capabilities and limitations, and appropriate measures will be taken to handle any encountered issues effectively.

### Security Considerations
Since the platform involves storing and processing sensitive user data, appropriate security measures will be implemented to ensure the confidentiality, integrity, and availability of the information. This will include encryption of sensitive data, implementing user authentication and authorization mechanisms, and adherence to data protection standards.

### Functionality
The platform will offer user registration and login functionality to provide personalized experiences and secure access to user-specific visualizations. Users will be able to create custom views, select data sources, choose visualization types, apply filters, and perform drilldowns for deeper analysis. Additionally, the platform will incorporate features for exporting and sharing visualizations, allowing users to collaborate and disseminate insights effectively.

### User Flow
The user flow will begin with user authentication or registration. Once logged in, users will have access to a dashboard where they can customize and save visualizations. They can select the data source, choose from different visualization/dashboards, configure filters, and interact with the visualizations to explore the data. The platform will provide intuitive navigation and clear instructions to guide users throughout their data analysis journey.

### Additional Features and Stretch Goals
To make the platform more than just CRUD (Create, Read, Update, Delete), I can consider incorporating features such as predictive analytics, outlier detection, and integration with external tools like Jupyter notebooks or Excel for advanced analysis. Stretch goals could include incorporating machine learning algorithms for automated insights generation or integrating with other data sources beyond Spotify.

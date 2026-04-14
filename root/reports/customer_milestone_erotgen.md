# Software Requirements Specification

## Objective

The purpose of this document is to eliminate any confusion that may arise while developing this project and to ensure that all stakeholders are on the same page.

## Scope

CulinaryGraph is a platform where users can share everything related to food in their region, including recipes, techniques, history, etc. Users can share food-related information specific to their regions on this platform, analyze data, or compare world cuisines.

## Target Audience

* Home Cooks
* Culinary Students
* Food Researchers
* Recipe Developers

## Functional Requirements

1. FR-1: The system shall allow users to register using an email address and password.
2. FR-2: When registering, users must provide their first name, last name, and email address.
3. FR-3: Before the user begins entering their registration information, they must fill out the date of birth, country, gender, and “About Me” sections. A profile photo is optional.
4. FR-4: The selected information of the country should not be changed again.
5. FR-5: At least one country must be added for each post.
6. FR-6: The system should not allow a new recipe with the same name to be created for the same region.
7. FR-7: To prevent the spread of misinformation and other inappropriate behavior, there should be a report page where users can report recipes.
8. FR-8: Reported posts and users are flagged for the admins.
9. FR-9: Administrators can ban reported users and delete reported posts.
10. FR-10: Administrators can lock pages containing disputed content.
11. FR-11: Posts made by users must be marked on the map.
12. FR-12: An interactive world map should be available for users who want to search by region, and recipes for the selected region should appear on this map.
13. FR-13: To enable data interpretation, the web application should support graph creation. Users should be able to create bar and pie charts with the data they want.
14. FR-14: User-based searches should be possible, and when a user's profile is accessed, information about which recipes they have contributed to and their location should be available.

## Non-Functional Requirements

1. NFR-1: The system shall return search results within 2 seconds.NFR-2: The system shall support up to 10,000 concurrent users.
2. NFR-3: The system shall replicate all database writes to at least two geographically distinct data centers.
3. NFR-4: All data transmission between client and server shall use TLS 1.2 or higher.
4. NFR-5: The system shall be fully functional on viewport widths from 320px (mobile) to 2560px (large desktop).

#Software Design (UML diagrams) 
https://github.com/Erotgen/2024719141-SWE-573-Software-Development-Practice/wiki/UML-Diagrams

#Scenarios and Mockups

## Scenario 1

Nermin Işık is a 34-year-old vegan from Hatay. She loves traditional vegan dishes and researches traditional vegan recipes from around the world. She logged into the CulinaryGraph web application to research recipes from other countries around the world. After signing up and logging in, the first thing she did was share the recipe for her favorite dish, falafel. While researching vegan recipes from other countries, she saw that someone from Lebanon had also shared a recipe for the same dish. The recipe was different from her own. She learned that this country also had its own unique falafel recipe. When Nermin closed the site, she knew more about the history of falafel and how it is prepared in different countries. 

## Scenario 2

Ayşe Demir is a 31-year-old food blogger from Gaziantep. She is passionate about kebab culture and how grilled meat dishes vary across different regions. She discovered the CulinaryGraph web application and decided to join. She registered using her Google account, filled in her profile details, and selected Gaziantep as her region. Once inside, she shared the recipe for her favorite dish, Antep kebab, with all its traditional details. Curious about kebab in other places, she explored the interactive world map and clicked on Iran, where she discovered a recipe for koobideh — a Persian-style kebab with saffron and onion that was quite different from her own. While browsing, she also came across a recipe with misleading historical claims and reported it. She then used the platform's charting tool to create a bar chart comparing kebab recipes across regions. Before closing the site, she searched for other contributors and found a user from Urfa whose profile showed all the recipes he had shared. By the end of the evening, Ayşe had a much richer understanding of how kebab traditions stretch across borders, each region preserving its own unique style.

#Project Plan, Communication Plan, Responsibility Assignment Matrix

#Main Contributions

Member: Mustafa Erötgen
Responsibilities: I was in charge of the entire project.
Main contributions: Writing code, designing, preparing diagrams and requirements, and deploying the code.

#Release Version
https://github.com/Erotgen/2024719141-SWE-573-Software-Development-Practice/releases/tag/swe573-customer-milestone

#Short Video Demo
Shared from Moodle.

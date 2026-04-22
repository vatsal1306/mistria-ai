# FRD

# **Functional Requirement Document (FRD)**

## **Project: AI Companion Platform Enhancement**

---

# **1\. Objective**

To restructure and enhance the existing system (built in Lovable) into a scalable product by:

* Migrating backend to Node.js  
* Improving user journey  
* Implementing token economy  
* Adding AI voice \+ avatar system  
* Building a structured admin panel

---

# **2\. Scope of Work**

## **2.1 Backend Migration**

### **Features**

* Complete backend transition to Node.js  
* API restructuring  
* Database optimization

### **Tasks**

**Backend**

* Setup Node.js architecture (MVC / modular)  
* Rewrite all APIs  
* Database schema restructuring  
* Authentication & session management  
* Integration with AI services (Mistral AI)

**Frontend**

* Update API integrations  
* Handle new response structures

---

# **2.2 Authentication & Registration Flow**

### **Updated Flow**

1. User Signup/Login  
2. Avatar Selection / Customization  
3. Avatar Preview  
4. Subscription Selection (Free Trial / Paid)  
5. Dashboard Entry

### **Tasks**

**Frontend**

* Redesign registration UI  
* Add avatar selection screen  
* Add preview screen  
* Subscription selection screen

**Backend**

* User registration APIs  
* Avatar mapping to user  
* Subscription assignment logic

---

# **2.3 Avatar (Companion) System**

### **Features**

* Select from active avatars (created by admin)  
* Customize avatar  
* View avatar personality & traits

### **Tasks**

**Frontend**

* Avatar listing UI  
* Avatar detail screen  
* Add/remove from “Interested”

**Backend**

* Avatar APIs  
* Mapping user ↔ avatar  
* Fetch avatar configurations

---

# **2.4 Raw Feed (Discovery Section)**

### **Features**

* List of available companions  
* Add to interested  
* Start conversation

### **Tasks**

**Frontend**

* Feed UI  
* Avatar cards  
* CTA: Chat / Add

**Backend**

* Fetch avatars  
* Interest tracking  
* Conversation initiation

---

# **2.5 Chat & Inbox System**

### **Features**

* Chat with multiple avatars  
* Inbox for all conversations

### **Tasks**

**Frontend**

* Chat UI  
* Inbox listing screen

**Backend**

* Chat session management  
* Message storage  
* Multi-avatar conversation handling

---

# **2.6 Voice Integration**

### **Features**

* Voice-based interaction with avatars

### **Tasks**

**Frontend**

* Voice input UI  
* Call/record interface

**Backend**

* Voice processing integration  
* AI voice response handling  
* Token deduction logic

---

# **2.7 Token System**

### **Features**

* Limited tokens for usage  
* Token consumption for:  
  * Chat  
  * Image generation  
  * Voice calls  
* Token top-up system

### **Tasks**

**Frontend**

* Token balance display  
* Token purchase screen  
* Token breakdown UI (e.g., X tokens \= $Y)

**Backend**

* Token wallet system  
* Deduction logic  
* Top-up handling  
* Usage tracking

---

# **2.8 Subscription Management**

### **Features**

* Free trial  
* Paid plans  
* Subscription validation

### **Tasks**

**Frontend**

* Subscription plans UI  
* Upgrade flow

**Backend**

* Subscription APIs  
* Plan validation  
* Payment gateway integration

---

# **2.9 Gallery Module**

### **Features**

* Store generated images  
* View past generated media

### **Tasks**

**Frontend**

* Gallery UI

**Backend**

* Image storage handling  
* Fetch user gallery

---

# **2.10 Connections System**

### **Features**

* Connection percentage with avatars  
* Increase/decrease based on chat

### **Tasks**

**Backend**

* Connection logic engine (to be provided by client)  
* Score calculation

**Frontend**

* Display connection %

---

# **2.11 Admin Panel**

---

## **2.11.1 Dashboard**

### **Features**

* Total Users  
* Total Avatars  
* Revenue

### **Tasks**

**Frontend**

* Dashboard UI

**Backend**

* Analytics APIs

---

## **2.11.2 User Management**

### **Features**

* List users  
* View user details

### **Tasks**

**Backend**

* User listing API  
* User detail API

**Frontend**

* Table UI

---

## **2.11.3 Avatar Management (Content)**

### **Features**

* Create avatar companion  
* Configure personality  
* Activate / Suspend avatar

### **Tasks**

**Backend**

* Avatar CRUD APIs

**Frontend**

* Avatar creation form  
* Avatar listing

---

## **2.11.4 Subscription Management**

### **Features**

* Create/manage plans  
* Configure pricing

### **Tasks**

**Backend**

* Plan APIs

**Frontend**

* Plan management UI

---

## **2.11.5 Token Management**

### **Features**

* Configure token pricing  
* Define usage rules

### **Tasks**

**Backend**

* Token configuration APIs

**Frontend**

* Token config UI

---

## **2.11.6 Transaction History**

### **Features**

* View payments  
* View token purchases

### **Tasks**

**Backend**

* Transaction APIs

**Frontend**

* Transaction table UI

---

## **2.11.7 Role-Based Access Control (RBAC)**

### **Features**

* Create roles  
* Assign permissions  
* Manage admin users

### **Tasks**

**Backend**

* RBAC system (roles \+ permissions)  
* Middleware for access control

**Frontend**

* Role management UI

---

# **2.12 Notifications**

### **Features**

* System notifications  
* Chat alerts

### **Tasks**

**Backend**

* Notification service

**Frontend**

* Notification UI

---

# **3\. Removed Features**

* “Her World” section  
* Application & Creator options

---

# **4\. External Integrations**

* AI Engine: Mistral AI  
* Payment Gateway (TBD)  
* Voice AI (TBD)

---

# **5\. Dependencies (Client Inputs Required)**

1. Connection logic definition  
2. Payment gateway credentials  
3. Token pricing configuration  
4. Token usage rules (per feature)

---

# **6\. Key Technical Considerations**

* Scalable Node.js backend  
* Token-based usage economy  
* AI integration latency handling  
* Real-time chat architecture  
* Secure payment handling

# User Journey

# **User Journey Document – AI Companion Platform**

---

# **1\. Authentication & Onboarding Journey**

### **1.1 User Signup / Login**

**Actor:** User

**Journey:**

1. User lands on Login / Signup screen  
2. User enters email, password (or social login)  
3. System validates credentials  
4. User account is created / authenticated

**System Behavior:**

* Create user profile  
* Initiate session  
* Redirect to onboarding flow (first-time users)

---

### **1.2 Avatar Selection / Customization**

**Actor:** User

**Journey:**

1. User is prompted to choose:  
   * Select existing avatar OR  
   * Customize new avatar  
2. User configures:  
   * Gender  
   * Appearance (eyes, hair, etc.)  
   * Personality traits  
3. User previews avatar

**System Behavior:**

* Store avatar preferences  
* Map avatar to user profile

---

### **1.3 Subscription Selection**

**Actor:** User

**Journey:**

1. User selects:  
   * Free Trial OR  
   * Paid Plan  
2. If paid:  
   * User proceeds to payment  
3. After selection → redirected to Dashboard

**System Behavior:**

* Assign plan to user  
* Initialize token balance (based on plan)

---

# **2\. Dashboard Journey**

**Actor:** User

**Journey:**

1. User lands on dashboard  
2. User sees:  
   * Token balance  
   * Active avatars  
   * Recent chats  
   * Quick actions

**System Behavior:**

* Fetch user summary data  
* Display personalized content

---

# **3\. Raw Feed (Discovery) Journey**

**Actor:** User

**Journey:**

1. User navigates to Raw Feed  
2. User views list of available avatars  
3. User actions:  
   * View avatar details  
   * Add to Interested  
   * Start conversation

**System Behavior:**

* Fetch active avatars (admin-created)  
* Initiate chat session on interaction

---

# **4\. Avatar Interaction Journey**

**Actor:** User

**Journey:**

1. User selects an avatar  
2. User starts conversation  
3. System checks:  
   * Token availability  
4. If tokens available:  
   * Chat continues  
5. If tokens exhausted:  
   * Prompt for top-up

**System Behavior:**

* Deduct tokens per message  
* Maintain conversation context

---

# **5\. Inbox (Multi-Chat) Journey**

**Actor:** User

**Journey:**

1. User opens Inbox  
2. User sees list of avatar new  conversations  
3. User selects a conversation  
4. User continues chat

**System Behavior:**

* Fetch all new chat sessions  
* Maintain unread/read status

---

# **6\. Voice Interaction Journey**

**Actor:** User

**Journey:**

1. User initiates voice interaction  
2. User speaks / records input  
3. System processes voice  
4. Avatar responds with voice

**System Behavior:**

* Convert speech to text  
* Send to AI engine  
* Convert response to voice  
* Deduct tokens

---

#  **7\. Token Management Journey**

### **7.1 Token Usage**

**Actor:** User

**Journey:**

* Tokens are consumed when:  
  1. Chatting  
  2. Image generation  
  3. Voice interaction

---

### **7.2 Token Exhaustion**

**Journey:**

1. User runs out of tokens  
2. System shows alert  
3. Redirect to Top-Up screen

---

### **7.3 Token Top-Up**

**Journey:**

1. User selects token package  
2. User completes payment  
3. Tokens are added

**System Behavior:**

* Update wallet  
* Log transaction

---

#    **8\. Gallery Journey**

**Actor:** User

**Journey:**

1. User navigates to Gallery  
2. User views generated images  
3. User can:  
   * View image

**System Behavior:**

* Fetch stored media  
* Map images to user

---

# **9\. Connection System Journey**

**Actor:** User

**Journey:**

1. User interacts with avatar  
2. System calculates connection score  
3. Score increases/decreases based on interaction

**System Behavior:**

* Apply connection logic (from client)  
* Update percentage dynamically

---

#   **10\. Notification Journey**

**Actor:** User

**Journey:**

1. User receives notifications for:  
   * Messages  
   * Token updates  
   * System alerts

**System Behavior:**

* Push/store notifications  
* Maintain notification history

---

# **11\. Admin Panel Journey**

---

## **11.1 Admin Authentication**

**Actor:** Admin

**Journey:**

1. Admin logs in  
2. Access dashboard

---

## **11.2 Dashboard Overview**

**Journey:**

1. Admin views:  
   * Total users  
   * Total avatars  
   * Revenue

---

## **11.3 User Management**

**Journey:**

1. Admin views user list  
2. Admin opens user details

---

## **11.4 Avatar (Content) Management**

**Journey:**

1. Admin creates new avatar  
2. Configures:  
   * Personality  
   * Appearance  
3. Publishes avatar  
4. Can suspend avatar

---

## **11.5 Subscription Management**

**Journey:**

1. Admin creates/updates plans  
2. Defines pricing

---

##     **11.6 Token Management**

**Journey:**

1. Admin defines:  
   * Token pricing  
   * Usage rules

---

## **11.7 Transaction Monitoring**

**Journey:**

1. Admin views transaction history  
2. Tracks revenue

---

## **11.8 Role-Based Access Control (RBAC)**

**Journey:**

1. Admin creates roles  
2. Assigns permissions  
3. Assigns roles to users

# AI user journey

# **Mistria – AI User Journey**

## **Purpose**

This document translates the existing **FRD** and **AI Implementation Plan** into a unified **AI-driven user journey**.

It is intended for the team to understand:

* What the AI is doing at each step  
* What inputs it needs  
* What outputs it produces  
* How the UI should react

---

# **1\. Onboarding – AI Companion Creation**

## **User Flow (Frontend)**

User selects:

* Gender / personality traits  
* Preferences (tone, style, interests)

## **AI Responsibilities**

* Generate a **companion persona**  
* Define:  
  * Personality (e.g., caring, playful, dominant)  
  * Tone of speech  
  * Conversational style  
* Generate **initial conversation seed**

## **AI Inputs**

* User-selected traits  
* Predefined personality templates

## **AI Outputs**

* Structured persona object:  
  * Name (if auto-generated)  
  * Personality attributes  
  * Tone rules  
* First message from companion  
* Prompt context for chat engine

---

# **2\. Chat System – Core Interaction Layer**

## **User Flow**

User chats with AI companion via text

## **AI Responsibilities**

* Generate context-aware responses  
* Maintain:  
  * Emotional continuity  
  * Personality consistency  
* Adapt responses based on:  
  * User tone  
  * Conversation history

## **AI Inputs**

* Current user message  
* User ID

## **AI Outputs**

* Text response  
* Optional metadata:  
  * Emotion tag (happy, caring, flirty, etc.)  
  * Intent classification

---

# **3\. Memory Layer – Personalization Engine**

## **User Flow**

User continues chatting over time

## **AI Responsibilities**

* Store important user information:  
  * Preferences  
  * Emotional patterns  
  * Key facts (names, likes, dislikes)  
* Retrieve memory during future conversations

## **AI Inputs**

* Conversation logs  
* Extracted key-value data

## **AI Outputs**

* Memory updates (structured)  
* Context injection into prompts

## **Frontend Implications**

* No direct UI required  
* Indirect impact:  
  * More personalized responses  
  * Continuity across sessions

---

#   **4\. Voice Interaction (TTS / Voice AI)**

## **User Flow**

User listens to AI responses

## **AI Responsibilities**

* Convert text → speech  
* Maintain tone consistency with persona

## **AI Inputs**

* AI-generated text  
* Selected voice profile

## **AI Outputs**

* Audio stream / file

## **Frontend Implications**

* Play audio alongside messages

---

# **5\. Token / Usage System**

## **User Flow**

User sends messages (limited by tokens)

## **AI Responsibilities**

* None. Token consumption to be handled by the frontend.

---

# **6\. Image Generation / Gallery**

## **User Flow**

* During onboarding: companion images generated  
* Gallery may display AI images

## **AI Responsibilities**

* Generate companion visuals (initial)

## **AI Inputs**

* Companion attributes

## **AI Outputs**

* Image(s)

## **Frontend Implications**

* Display generated images  
* Store in gallery view

---

# **7\. Notifications & Re-engagement**

## **User Flow**

User leaves app → returns later

## **AI Responsibilities**

* Generate re-engagement messages:  
  * “I missed you”  
  * Context-aware nudges

## **AI Inputs**

* Last interaction  
* Time gap  
* User behavior

## **AI Outputs**

* Notification text

## **Frontend Implications**

* Push notifications  
* Re-entry message in chat

---

# **8\. Connection Score / Relationship Layer**

## **User Flow**

User builds relationship with AI

## **AI Responsibilities**

* Provide signals (optional):  
  * Engagement level  
  * Emotional tone

## **AI Inputs**

* Conversation patterns

## **AI Outputs**

* Signals for scoring (if implemented)

## **Frontend Implications**

* Display connection score (if exists)

## **Notes / Gaps**

* Logic defined as **client-side (FRD)**  
* AI role unclear

---

# 

# **9\. Admin & Control Layer**

## **User Flow**

(Not user-facing)

## **AI Responsibilities**

* Respect configurable parameters:  
  * Personality tuning  
  * Safety filters  
  * Prompt templates

## **AI Inputs**

* Admin-defined configs

## **AI Outputs**

* Behavior adjustments

## **Frontend Implications**

* None directly  
* Impacts AI behavior globally

---

# **10\. AI-specific Risks**

* This system will require significant research and development due to the constraint of not utilizing third-party API-based models and instead relying entirely on self-hosted AI architectures.   
* As a result, overall performance, response quality, and contextual accuracy will be directly dependent on the capabilities of the selected open-source models, as well as the effectiveness of fine-tuning, prompt engineering, and ongoing optimization.  
* Variability in model behavior should be expected, and achieving production-grade reliability will require iterative improvements across model selection, training strategies, and infrastructure.  
* More details on AI implementation and Risks available [here](https://docs.google.com/document/d/11vOK6zndrHwXYtYTKt5hAxXtpTxCrTOxcKXpHTpGXLk/edit?usp=sharing).


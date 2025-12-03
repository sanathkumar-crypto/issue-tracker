# Issue Tracker

A hospital/healthcare issue tracking system built with Firebase and vanilla JavaScript.

## Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/sanathkumar-crypto/issue-tracker.git
   cd issue-tracker
   ```

2. **Configure Firebase**
   - Copy `config.example.js` to `config.js`
   ```bash
   cp config.example.js config.js
   ```
   - Open `config.js` and fill in your Firebase configuration:
     - `apiKey`: Your Firebase API key
     - `authDomain`: Your Firebase auth domain
     - `projectId`: Your Firebase project ID
     - `storageBucket`: Your Firebase storage bucket
     - `messagingSenderId`: Your Firebase messaging sender ID
     - `appId`: Your Firebase app ID
     - `measurementId`: Your Firebase measurement ID

3. **Important Security Notes**
   - `config.js` is gitignored and should **never** be committed to the repository
   - Keep your Firebase credentials secure
   - Only `@cloudphysician.net` email addresses are allowed to log in

## Running Locally

Simply serve the `index.html` file using any HTTP server:

```bash
# Using Python
python3 -m http.server 8000

# Using Node.js (if you have http-server installed)
npx http-server -p 8000
```

Then open `http://localhost:8000` in your browser.

## Features

- Google Sign-In authentication (restricted to cloudphysician.net domain)
- Issue/Task management with status workflow
- Real-time updates via Firebase
- File attachments and comments
- Dashboard with statistics and charts
- Admin panel for user and hospital management
- Google Chat notifications

## License

Private - All rights reserved
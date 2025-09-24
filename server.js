const express = require('express');
const path = require('path');
const app = express();
const port = 3001;

// Serve static files
app.use(express.static(__dirname));

// Serve the main HTML file
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'twitter_feed.html'));
});

// Start the server
app.listen(port, () => {
  console.log(`Twitter Feed application running at http://localhost:${port}`);
}); 
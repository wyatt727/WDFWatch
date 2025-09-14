// Constants
const RESPONSE_JSON_PATH = 'transcripts/responses.json';
const BOT_NAME = 'WDF Bot';
const BOT_HANDLE = '@WDF_Watch';
const MAX_CHAR_LIMIT = 280; // Twitter character limit

// DOM Elements
const tweetFeed = document.getElementById('tweet-feed');
const loading = document.getElementById('loading');

// Function to format date
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

// Function to get initials from username
function getInitials(username) {
    if (!username) return "?";
    // Remove @ symbol if it exists
    const name = username.replace('@', '');
    // Get the first character, or first and last if there are multiple words
    const parts = name.split(/[^a-zA-Z0-9]/);
    if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
    return (parts[0].charAt(0) + parts[parts.length-1].charAt(0)).toUpperCase();
}

// Function to truncate text to character limit with ellipsis
function truncateText(text, limit) {
    if (!text || text.length <= limit) return text;
    // Always truncate at a space if possible
    let end = limit - 5;
    while (end > limit - 20 && text.charAt(end) !== ' ' && end > 0) {
        end--;
    }
    // If we couldn't find a space, just truncate at the limit
    if (end === 0 || text.charAt(end) !== ' ') {
        end = limit - 5;
    }
    return text.substring(0, end) + '... ';
}

// Function to check if text needs truncation
function needsTruncation(text) {
    return text && text.length > MAX_CHAR_LIMIT;
}

// Function to auto-resize textarea to fit content
function autoResizeTextarea(textarea) {
    // Reset height to allow proper scrollHeight calculation
    textarea.style.height = 'auto';
    // Set the height to match the scroll height
    textarea.style.height = (textarea.scrollHeight) + 'px';
}

// Function to create a tweet element
function createTweetElement(tweet) {
    const tweetElement = document.createElement('div');
    tweetElement.className = 'tweet';
    
    // Format the date
    const formattedDate = formatDate(tweet.created_at);
    
    // Get user initials for avatar
    const userInitials = getInitials(tweet.user);
    
    // Check if tweet text needs truncation
    const isTweetTruncated = needsTruncation(tweet.text);
    // Truncate tweet text if needed
    const tweetText = isTweetTruncated ? truncateText(tweet.text, MAX_CHAR_LIMIT) : tweet.text;
    
    // Create tweet HTML structure
    tweetElement.innerHTML = `
        <div class="tweet-header">
            <div class="avatar">${userInitials}</div>
            <div class="tweet-user">
                <div class="user-name">User</div>
                <div class="user-handle">${tweet.user}</div>
            </div>
            <div class="tweet-timestamp">${formattedDate}</div>
        </div>
        <div class="tweet-body">
            <span class="tweet-text ${isTweetTruncated ? 'truncated' : ''}">${tweetText}</span>
            ${isTweetTruncated ? 
                '<span class="truncated-indicator" data-action="expand-tweet"><i class="fas fa-plus-circle"></i> Show more</span>' : ''}
        </div>
        <div class="tweet-actions">
            <div class="action-button">
                <i class="far fa-comment"></i>
                <span>Reply</span>
            </div>
            <div class="action-button">
                <i class="fas fa-retweet"></i>
                <span>Retweet</span>
            </div>
            <div class="action-button">
                <i class="far fa-heart"></i>
                <span>Like</span>
            </div>
            <div class="action-button">
                <i class="far fa-share-square"></i>
                <span>Share</span>
            </div>
        </div>
    `;
    
    // If there's a response, add it
    if (tweet.response && tweet.response.trim() !== '') {
        const responseElement = document.createElement('div');
        responseElement.className = 'response';
        
        // Check if response text needs truncation
        const isResponseTruncated = needsTruncation(tweet.response);
        // Truncate response text if needed
        const responseText = isResponseTruncated ? truncateText(tweet.response, MAX_CHAR_LIMIT) : tweet.response;
        
        responseElement.innerHTML = `
            <div class="response-header">
                <div class="response-avatar">WDF</div>
                <div class="response-user">${BOT_NAME} <span class="user-handle">${BOT_HANDLE}</span></div>
                <div class="edit-response-btn" title="Edit Response"><i class="fas fa-edit"></i></div>
            </div>
            <div class="response-body">
                <span class="response-text ${isResponseTruncated ? 'truncated' : ''}" data-full-text="${tweet.response}">${responseText}</span>
                ${isResponseTruncated ? 
                    '<span class="truncated-indicator" data-action="expand-response"><i class="fas fa-plus-circle"></i> Show more</span>' : ''}
            </div>
            <div class="response-actions">
                <button class="post-reply-btn"><i class="far fa-paper-plane"></i> Post Reply</button>
            </div>
            <div class="edit-response-container" style="display: none;">
                <textarea class="edit-response-textarea">${tweet.response}</textarea>
                <div class="edit-response-actions">
                    <button class="save-edit-btn">Save</button>
                    <button class="cancel-edit-btn">Cancel</button>
                </div>
            </div>
        `;
        tweetElement.appendChild(responseElement);
    }
    
    // Add click event handler for expanding truncated text
    if (isTweetTruncated) {
        setTimeout(() => {
            const expandTweetBtn = tweetElement.querySelector('[data-action="expand-tweet"]');
            if (expandTweetBtn) {
                expandTweetBtn.addEventListener('click', () => {
                    const tweetTextElement = tweetElement.querySelector('.tweet-text');
                    tweetTextElement.textContent = tweet.text;
                    tweetTextElement.classList.remove('truncated');
                    expandTweetBtn.style.display = 'none';
                });
            }
        }, 0);
    }
    
    // Add click event handler for expanding truncated response
    if (tweet.response && needsTruncation(tweet.response)) {
        setTimeout(() => {
            const responseElement = tweetElement.querySelector('.response');
            const expandResponseBtn = responseElement.querySelector('[data-action="expand-response"]');
            if (expandResponseBtn) {
                expandResponseBtn.addEventListener('click', () => {
                    const responseTextElement = responseElement.querySelector('.response-text');
                    responseTextElement.textContent = tweet.response;
                    responseTextElement.classList.remove('truncated');
                    expandResponseBtn.style.display = 'none';
                });
            }
        }, 0);
    }
    
    // Add event handlers for editing responses
    if (tweet.response) {
        setTimeout(() => {
            const responseElement = tweetElement.querySelector('.response');
            
            // Edit response button
            const editBtn = responseElement.querySelector('.edit-response-btn');
            const responseText = responseElement.querySelector('.response-text');
            const editContainer = responseElement.querySelector('.edit-response-container');
            const editTextarea = responseElement.querySelector('.edit-response-textarea');
            const saveBtn = responseElement.querySelector('.save-edit-btn');
            const cancelBtn = responseElement.querySelector('.cancel-edit-btn');
            
            // Auto-resize the textarea initially
            autoResizeTextarea(editTextarea);
            
            // Add input event listener to auto-resize as user types
            editTextarea.addEventListener('input', () => {
                autoResizeTextarea(editTextarea);
            });
            
            editBtn.addEventListener('click', () => {
                const fullText = responseText.getAttribute('data-full-text') || responseText.textContent;
                editTextarea.value = fullText;
                responseText.parentElement.style.display = 'none';
                editContainer.style.display = 'block';
                // Auto-resize when showing the textarea
                autoResizeTextarea(editTextarea);
                editTextarea.focus();
            });
            
            saveBtn.addEventListener('click', () => {
                const newResponse = editTextarea.value.trim();
                if (newResponse) {
                    // Update the displayed text
                    const isTruncated = needsTruncation(newResponse);
                    responseText.setAttribute('data-full-text', newResponse);
                    
                    if (isTruncated) {
                        responseText.textContent = truncateText(newResponse, MAX_CHAR_LIMIT);
                        responseText.classList.add('truncated');
                        
                        // If there's no "show more" button yet, add it
                        if (!responseElement.querySelector('[data-action="expand-response"]')) {
                            const expandBtn = document.createElement('span');
                            expandBtn.className = 'truncated-indicator';
                            expandBtn.setAttribute('data-action', 'expand-response');
                            expandBtn.innerHTML = '<i class="fas fa-plus-circle"></i> Show more';
                            responseText.parentElement.appendChild(expandBtn);
                            
                            expandBtn.addEventListener('click', () => {
                                responseText.textContent = newResponse;
                                responseText.classList.remove('truncated');
                                expandBtn.style.display = 'none';
                            });
                        }
                    } else {
                        responseText.textContent = newResponse;
                        responseText.classList.remove('truncated');
                        
                        // Remove "show more" button if it exists
                        const expandBtn = responseElement.querySelector('[data-action="expand-response"]');
                        if (expandBtn) {
                            expandBtn.remove();
                        }
                    }
                    
                    // Update the tweet object (in memory only)
                    tweet.response = newResponse;
                }
                
                responseText.parentElement.style.display = 'block';
                editContainer.style.display = 'none';
            });
            
            cancelBtn.addEventListener('click', () => {
                responseText.parentElement.style.display = 'block';
                editContainer.style.display = 'none';
            });
            
            // Post Reply button
            const postReplyBtn = responseElement.querySelector('.post-reply-btn');
            postReplyBtn.addEventListener('click', function() {
                // Add posted class and change text permanently
                this.classList.add('posted');
                this.innerHTML = '<i class="fas fa-check"></i> Reply Posted!';
                
                // No timeout to reset - button stays green permanently
            });
        }, 0);
    }
    
    return tweetElement;
}

// Function to load and parse the responses.json file
async function loadResponses() {
    try {
        const response = await fetch(RESPONSE_JSON_PATH);
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        
        const data = await response.json();
        
        // Filter for only 'RELEVANT' tweets
        const relevantTweets = data.filter(tweet => tweet.classification === 'RELEVANT');
        
        // Hide loading spinner
        loading.style.display = 'none';
        
        // Display tweets
        if (relevantTweets.length === 0) {
            tweetFeed.innerHTML = '<p class="no-tweets">No relevant tweets found.</p>';
            return;
        }
        
        // Sort tweets by date (newest first)
        relevantTweets.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        
        // Create and append tweet elements
        relevantTweets.forEach(tweet => {
            const tweetElement = createTweetElement(tweet);
            tweetFeed.appendChild(tweetElement);
        });
        
        // Log to help with debugging
        console.log(`Loaded ${relevantTweets.length} relevant tweets`);
        console.log(`Tweets with truncated content: ${relevantTweets.filter(t => needsTruncation(t.text)).length}`);
        console.log(`Responses with truncated content: ${relevantTweets.filter(t => needsTruncation(t.response)).length}`);
        
    } catch (error) {
        console.error('Error loading responses:', error);
        loading.style.display = 'none';
        tweetFeed.innerHTML = `<p class="error">Failed to load tweets: ${error.message}</p>`;
    }
}

// Initialize the application
document.addEventListener('DOMContentLoaded', () => {
    loadResponses();
}); 
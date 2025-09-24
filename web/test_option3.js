// Test script for Option 3 implementation
const fetch = require('node-fetch');

async function testOption3() {
  console.log('Testing Option 3: exec() with zsh shell');
  console.log('Episode: it-wasnt-the-last');
  console.log('Stage: summarization');
  console.log('Time:', new Date().toISOString());
  console.log('----------------------------');

  try {
    const response = await fetch('http://localhost:8888/api/episodes/31/pipeline/run', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        stageId: 'summarization',
        force: true
      })
    });

    const data = await response.json();
    console.log('Response:', data);

    if (response.ok) {
      console.log('✅ Pipeline started successfully!');
      console.log('Run ID:', data.runId);
      console.log('Monitor logs for progress...');
    } else {
      console.log('❌ Failed to start pipeline:', data.error);
    }
  } catch (error) {
    console.error('Error calling API:', error);
  }
}

testOption3();
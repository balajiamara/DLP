const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const ARTIFACT_DIR = 'C:\\Users\\balaj\\.gemini\\antigravity-ide\\brain\\d06ed339-2682-4042-8f74-47077198b87a';

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function runTest() {
  console.log('=== Starting E2E Unified Chat Live Verification ===');
  
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,800'],
  });

  try {
    const contextStudent = await browser.createBrowserContext();
    const pageStudent = await contextStudent.newPage();
    await pageStudent.setViewport({ width: 1280, height: 1000 });

    pageStudent.on('console', (msg) => console.log(`[BROWSER CONSOLE] ${msg.type()}: ${msg.text()}`));
    pageStudent.on('pageerror', (err) => console.error(`[BROWSER ERROR]`, err));

    console.log('1. Student Logging in at http://localhost:5173/login...');
    await pageStudent.goto('http://localhost:5173/login', { waitUntil: 'networkidle0' });
    await pageStudent.type('input[type="email"]', 'test2@gmail.com');
    await pageStudent.type('input[type="password"]', 'testpass123');
    await pageStudent.click('button[type="submit"]');

    await pageStudent.waitForNavigation({ waitUntil: 'networkidle0' });
    console.log('Student logged in successfully, current URL:', pageStudent.url());

    // 2. Navigate to Classroom 6
    console.log('2. Navigating to Classroom 6 (http://localhost:5173/classrooms/6)...');
    await pageStudent.goto('http://localhost:5173/classrooms/6', { waitUntil: 'networkidle0' });
    await delay(1500);

    // 3. Click Classroom Chat tab
    console.log('3. Clicking Classroom Chat tab (#tab-classroom-chat)...');
    await pageStudent.waitForSelector('#tab-classroom-chat', { timeout: 5000 });
    await pageStudent.click('#tab-classroom-chat');

    // Wait for chat container and message elements to render
    console.log('Waiting for #chat-messages-container and message elements...');
    await pageStudent.waitForSelector('#chat-messages-container', { timeout: 10000 });
    await pageStudent.waitForSelector('div[id^="chat-message-"]', { timeout: 15000 });
    await delay(1500);

    // Scroll window down so chat container is in focus
    await pageStudent.evaluate(() => {
      const el = document.getElementById('chat-messages-container');
      if (el) el.scrollIntoView({ behavior: 'instant', block: 'center' });
    });
    await delay(500);

    // Screenshot 1: Chat tab with message history
    const screenshot1Path = path.join(ARTIFACT_DIR, 'screenshot1_chat_history.png');
    await pageStudent.screenshot({ path: screenshot1Path, fullPage: false });
    console.log('>>> [Screenshot 1 Saved]:', screenshot1Path);

    // 4. Scroll up and click "Load earlier messages"
    console.log('4. Scrolling to top of chat container to inspect earlier messages...');
    await pageStudent.evaluate(() => {
      const container = document.getElementById('chat-messages-container');
      if (container) container.scrollTop = 0;
    });
    await delay(1000);

    const loadMoreBtn = await pageStudent.$('#load-earlier-messages-btn');
    if (loadMoreBtn) {
      console.log('Clicking #load-earlier-messages-btn...');
      await loadMoreBtn.click();
      await delay(2000); // Wait for earlier messages to fetch and prepend
    } else {
      console.log('Note: All messages already loaded or button not present.');
    }

    // Screenshot 3: Scroll-up "load older messages" behavior
    const screenshot3Path = path.join(ARTIFACT_DIR, 'screenshot3_load_older.png');
    await pageStudent.screenshot({ path: screenshot3Path, fullPage: false });
    console.log('>>> [Screenshot 3 Saved]:', screenshot3Path);

    // 5. Scroll back down to bottom before receiving live message
    console.log('5. Scrolling Student back to bottom...');
    await pageStudent.evaluate(() => {
      const container = document.getElementById('chat-messages-container');
      if (container) container.scrollTop = container.scrollHeight;
    });
    await delay(1000);

    // 6. Session 1 (Teacher 'tester') sends a live message via Django REST API
    console.log('6. Session 1 (Teacher) sending real-time message via Django REST API...');
    const teacherMsgBody = `🚀 LIVE WEBSOCKET BROADCAST from Teacher! (Timestamp: ${Date.now()})`;
    
    const postStatus = await pageStudent.evaluate(async (bodyText) => {
      const authRes = await fetch('http://127.0.0.1:8000/api/auth/token/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'test@gmail.com', password: 'testpass123' }),
      });
      const authData = await authRes.json();
      
      const msgRes = await fetch('http://127.0.0.1:8000/api/conversations/6/messages/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authData.access}`,
        },
        body: JSON.stringify({ body: bodyText }),
      });
      return msgRes.status;
    }, teacherMsgBody);

    console.log('Teacher message REST POST status:', postStatus);

    // 7. Wait for the message to arrive in Student's UI via WebSocket without refresh
    console.log('7. Waiting for live WebSocket message arrival in Student UI...');
    await pageStudent.waitForFunction(
      (expectedText) => {
        const container = document.getElementById('chat-messages-container');
        return container && container.innerText.includes(expectedText);
      },
      { timeout: 10000 },
      teacherMsgBody
    );
    console.log('>>> LIVE WEBSOCKET EVENT RECEIVED IN STUDENT SESSION WITHOUT REFRESH!');
    await pageStudent.evaluate(() => {
      const el = document.getElementById('chat-messages-container');
      if (el) {
        el.scrollIntoView({ behavior: 'instant', block: 'center' });
        el.scrollTop = el.scrollHeight;
      }
    });
    await delay(1000);

    // Screenshot 2: Live arrival moment
    const screenshot2Path = path.join(ARTIFACT_DIR, 'screenshot2_live_arrival.png');
    await pageStudent.screenshot({ path: screenshot2Path, fullPage: false });
    console.log('>>> [Screenshot 2 Saved]:', screenshot2Path);

    // 8. Fresh Study Group Empty State & Group Chat
    console.log('8. Navigating to Study Group 1 (http://localhost:5173/groups/1)...');
    await pageStudent.goto('http://localhost:5173/groups/1', { waitUntil: 'networkidle0' });
    await delay(2000);

    // Scroll down to group chat section
    await pageStudent.evaluate(() => {
      window.scrollTo(0, document.body.scrollHeight);
    });
    await delay(1000);

    // Screenshot 4: Empty state for a fresh conversation
    const screenshot4Path = path.join(ARTIFACT_DIR, 'screenshot4_empty_state.png');
    await pageStudent.screenshot({ path: screenshot4Path, fullPage: false });
    console.log('>>> [Screenshot 4 Saved]:', screenshot4Path);

    // 9. Send message in Group Chat as Student
    console.log('9. Sending message in Study Group chat...');
    await pageStudent.waitForSelector('#chat-message-input', { timeout: 5000 });
    await pageStudent.type('#chat-message-input', 'Hello peer study group members! Ready to discuss algorithms.');
    await pageStudent.click('#chat-send-btn');
    await delay(1500);

    // 10. Teacher sends live reply into Study Group 1 via REST API
    console.log('10. Teacher sending live reply into Study Group 1 via REST API...');
    const groupReplyBody = `Welcome everyone! Let's solve LeetCode problems together. (Time: ${Date.now()})`;
    await pageStudent.evaluate(async (bodyText) => {
      const authRes = await fetch('http://127.0.0.1:8000/api/auth/token/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: 'test@gmail.com', password: 'testpass123' }),
      });
      const authData = await authRes.json();
      
      await fetch('http://127.0.0.1:8000/api/conversations/8/messages/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authData.access}`,
        },
        body: JSON.stringify({ body: bodyText }),
      });
    }, groupReplyBody);

    // 11. Wait for live arrival of Teacher message in group chat
    console.log('11. Waiting for live arrival in Group Chat...');
    await pageStudent.waitForFunction(
      (expectedText) => {
        const container = document.getElementById('chat-messages-container');
        return container && container.innerText.includes(expectedText);
      },
      { timeout: 10000 },
      groupReplyBody
    );
    console.log('>>> GROUP CHAT LIVE WEBSOCKET EVENT RECEIVED CLEANLY!');
    await delay(1000);

    const screenshot5Path = path.join(ARTIFACT_DIR, 'screenshot5_group_chat_live.png');
    await pageStudent.screenshot({ path: screenshot5Path, fullPage: false });
    console.log('>>> [Group Chat Screenshot Saved]:', screenshot5Path);

    console.log('\n======================================================');
    console.log('  ALL BROWSER E2E LIVE VERIFICATION CHECKS PASSED!    ');
    console.log('======================================================\n');
  } finally {
    await browser.close();
  }
}

runTest().catch((err) => {
  console.error('E2E Test Failed:', err);
  process.exit(1);
});

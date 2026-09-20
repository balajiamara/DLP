const puppeteer = require('puppeteer-core');
const path = require('path');
const fs = require('fs');

const CHROME_PATH = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const ARTIFACT_DIR = 'C:\\Users\\balaj\\.gemini\\antigravity-ide\\brain\\d06ed339-2682-4042-8f74-47077198b87a';

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function runTest() {
  console.log('=== Starting E2E Unified Chat Direct Messages (DM) Live Verification ===');

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1280,850'],
  });

  try {
    // -------------------------------------------------------------
    // Session 2: Student (tester2)
    // -------------------------------------------------------------
    const contextStudent = await browser.createBrowserContext();
    const pageStudent = await contextStudent.newPage();
    await pageStudent.setViewport({ width: 1280, height: 850 });

    pageStudent.on('console', (msg) => console.log(`[STUDENT CONSOLE] ${msg.type()}: ${msg.text()}`));
    pageStudent.on('pageerror', (err) => console.error(`[STUDENT ERROR]`, err));

    console.log('1. Student Logging in at http://localhost:5173/login...');
    await pageStudent.goto('http://localhost:5173/login', { waitUntil: 'networkidle0' });
    await pageStudent.type('input[type="email"]', 'test2@gmail.com');
    await pageStudent.type('input[type="password"]', 'testpass123');
    await pageStudent.click('button[type="submit"]');

    await pageStudent.waitForNavigation({ waitUntil: 'networkidle0' });
    console.log('Student logged in successfully, navigating to /messages...');

    await pageStudent.goto('http://localhost:5173/messages', { waitUntil: 'networkidle0' });
    await delay(2000);

    // Screenshot 1: Inbox view with a mix of conversation types
    console.log('Taking Screenshot 1: Inbox view with conversation types...');
    const screenshot1Path = path.join(ARTIFACT_DIR, 'screenshot1_inbox_view.png');
    await pageStudent.screenshot({ path: screenshot1Path, fullPage: false });
    console.log('>>> [Screenshot 1 Saved]:', screenshot1Path);

    // -------------------------------------------------------------
    // Session 1: Teacher (tester)
    // -------------------------------------------------------------
    const contextTeacher = await browser.createBrowserContext();
    const pageTeacher = await contextTeacher.newPage();
    await pageTeacher.setViewport({ width: 1280, height: 850 });

    pageTeacher.on('console', (msg) => console.log(`[TEACHER CONSOLE] ${msg.type()}: ${msg.text()}`));
    pageTeacher.on('pageerror', (err) => console.error(`[TEACHER ERROR]`, err));

    console.log('2. Teacher Logging in at http://localhost:5173/login...');
    await pageTeacher.goto('http://localhost:5173/login', { waitUntil: 'networkidle0' });
    await pageTeacher.type('input[type="email"]', 'test@gmail.com');
    await pageTeacher.type('input[type="password"]', 'testpass123');
    await pageTeacher.click('button[type="submit"]');

    await pageTeacher.waitForNavigation({ waitUntil: 'networkidle0' });
    console.log('Teacher logged in successfully, navigating to /messages...');

    await pageTeacher.goto('http://localhost:5173/messages', { waitUntil: 'networkidle0' });
    await delay(1500);

    // Teacher clicks "New DM" button
    console.log('Teacher clicking #new-dm-btn...');
    await pageTeacher.waitForSelector('#new-dm-btn', { timeout: 5000 });
    await pageTeacher.click('#new-dm-btn');

    // Wait for search input in modal
    console.log('Waiting for #user-search-input...');
    await pageTeacher.waitForSelector('#user-search-input', { timeout: 5000 });
    await pageTeacher.type('#user-search-input', 'tester2');

    // Wait for debounced search results to return tester2
    console.log('Waiting for #user-search-result-tester2...');
    await pageTeacher.waitForSelector('#user-search-result-tester2', { timeout: 8000 });
    await delay(1000);

    // Screenshot 2: Username search in action
    console.log('Taking Screenshot 2: Username search in action...');
    const screenshot2Path = path.join(ARTIFACT_DIR, 'screenshot2_username_search.png');
    await pageTeacher.screenshot({ path: screenshot2Path, fullPage: false });
    console.log('>>> [Screenshot 2 Saved]:', screenshot2Path);

    // Teacher selects tester2 to start/open the direct conversation
    console.log('Teacher selecting tester2 to create/open DM...');
    await pageTeacher.click('#user-search-result-tester2');
    await delay(2000);

    // Wait for ChatView to mount for the DM in Teacher's session
    console.log('Waiting for Teacher ChatView to mount (#chat-messages-container)...');
    await pageTeacher.waitForSelector('#chat-messages-container', { timeout: 10000 });
    await pageTeacher.waitForSelector('#chat-message-input', { timeout: 10000 });
    await delay(1000);

    // Screenshot 3: Open DM conversation in Session 1
    console.log('Taking Screenshot 3: Open DM conversation...');
    const screenshot3Path = path.join(ARTIFACT_DIR, 'screenshot3_open_dm_conversation.png');
    await pageTeacher.screenshot({ path: screenshot3Path, fullPage: false });
    console.log('>>> [Screenshot 3 Saved]:', screenshot3Path);

    // -------------------------------------------------------------
    // Open the same DM in Session 2 (Student tester2)
    // -------------------------------------------------------------
    console.log('3. Student opening the DM conversation in Session 2...');
    // In Session 2, refresh conversations or click the newly created DM row
    await pageStudent.goto('http://localhost:5173/messages', { waitUntil: 'networkidle0' });
    await delay(1500);

    // Find and click the DM row with tester
    console.log('Student selecting conversation with tester via button[data-type="DIRECT"]...');
    await pageStudent.waitForSelector('button[data-type="DIRECT"]', { timeout: 10000 });
    await pageStudent.click('button[data-type="DIRECT"]');
    console.log('Direct message conversation row clicked by Student!');
    await delay(2000);

    // Ensure Student's ChatView is ready and WebSocket connected
    await pageStudent.waitForSelector('#chat-messages-container', { timeout: 10000 });
    await pageStudent.waitForSelector('#chat-message-input', { timeout: 10000 });
    console.log('Student ChatView mounted and listening for WebSocket events.');

    // -------------------------------------------------------------
    // Session 1 (Teacher) sends a message live
    // -------------------------------------------------------------
    const teacherMsg = `Hello tester2! Direct message real-time WebSocket delivery test. [${Date.now()}]`;
    console.log(`4. Teacher sending message: "${teacherMsg}"`);
    await pageTeacher.type('#chat-message-input', teacherMsg);
    await pageTeacher.click('#chat-send-btn');
    await delay(500);

    // Wait for the message to appear live in Student's DOM without refreshing
    console.log('5. Waiting for live arrival in Student session (WITHOUT refresh)...');
    await pageStudent.waitForFunction(
      (text) => {
        const container = document.getElementById('chat-messages-container');
        return container && container.innerText.includes(text);
      },
      { timeout: 10000 },
      teacherMsg
    );
    console.log('>>> SUCCESS: Teacher message arrived LIVE in Student session via WebSocket!');

    // Student sends a reply
    const studentReply = `Hello Teacher! Received your direct message live without any page reload!`;
    console.log(`6. Student sending reply: "${studentReply}"`);
    await pageStudent.type('#chat-message-input', studentReply);
    await pageStudent.click('#chat-send-btn');
    await delay(1500);

    // Screenshot 4: Live arrival moment in the second session
    console.log('Taking Screenshot 4: Live arrival moment in the second session...');
    const screenshot4Path = path.join(ARTIFACT_DIR, 'screenshot4_live_arrival.png');
    await pageStudent.screenshot({ path: screenshot4Path, fullPage: false });
    console.log('>>> [Screenshot 4 Saved]:', screenshot4Path);

    console.log('=== All 4 E2E Live Verification Screenshots Captured Successfully! ===');
  } catch (err) {
    console.error('E2E Test Failed:', err);
    throw err;
  } finally {
    await browser.close();
  }
}

runTest().catch((err) => {
  console.error(err);
  process.exit(1);
});

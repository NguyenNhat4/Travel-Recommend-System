import { expect, test } from '@playwright/test';
import completed from '../../../shared/mocks/itinerary-agent/completed.json' with { type: 'json' };

const openingPlaceholder = 'Mô tả chuyến đi bạn mong muốn…';

for (const width of [390,1024]) {
  test(`ten requested recommendations render without clipping at ${width}px`, async ({page}) => {
    const {default:response}=await import('../../../shared/mocks/itinerary-agent/explore-ten.json',{with:{type:'json'}});
    await page.setViewportSize({width,height:900});
    const scope={intent:'more',scopeMode:'replace',requestedCount:10};
    const progress={turnKind:'explore',steps:['understand','search','write'],completedStep:'write',
      understood:{jobs:[{groupId:'job:1',kind:'hotel',scope}]},
      searches:[{groupId:'job:1',kind:'hotel',status:'ok',scope,counts:{inScope:10,chosen:10}}]};
    await page.route('**/api/v1/assistant/itineraries/stream', route => route.fulfill({contentType:'text/event-stream',
      body:`event: node.completed\ndata: ${JSON.stringify({nodeId:'run_jobs',progress})}\n\nevent: run.completed\ndata: ${JSON.stringify({response})}\n\n`}));
    await page.goto('/');
    await page.getByRole('button',{name:'Mở trợ lý du lịch AI'}).click();
    const dialog=page.getByRole('dialog',{name:'Trợ lý du lịch AI'});
    await dialog.getByPlaceholder(openingPlaceholder).fill('Giới thiệu 10 khách sạn');
    await dialog.getByRole('button',{name:'Gửi yêu cầu'}).click();
    await expect(dialog.getByRole('button',{name:/^Xem chi tiết /})).toHaveCount(10);
    await dialog.getByRole('button',{name:/Xem các bước/}).click();
    await expect(dialog.getByText(/bỏ phạm vi thành phố cũ để tìm ở nhiều điểm đến/)).toBeVisible();
    await expect(dialog.getByText(/Mục tiêu là 10 lựa chọn/)).toBeVisible();
    expect(await dialog.evaluate(el => el.scrollWidth>el.clientWidth)).toBe(false);
    await dialog.getByRole('button',{name:`Xem chi tiết ${response.searchResults.hotel[9].name}`,exact:true}).scrollIntoViewIfNeeded();
    await expect(dialog.getByRole('button',{name:`Xem chi tiết ${response.searchResults.hotel[9].name}`,exact:true})).toBeVisible();
    await dialog.screenshot({path:`/tmp/travel-ten-recommendations-${width}.png`,animations:'disabled'});
  });
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/auth/session', (route) => route.fulfill({ json: { state: 'anonymous' } }));
  await page.route('**/api/v1/products?**', (route) => route.fulfill({ json: { results: [], total: 0, limit: 10, offset: 0 } }));
});

for (const width of [320, 768, 1024, 1440]) {
  test(`opening is usable at ${width}px without sending a request`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    const errors: string[] = [];
    page.on('pageerror', (error) => errors.push(error.message));
    let requests = 0;
    let destinationRequests = 0;
    await page.route('**/api/v1/assistant/itineraries/stream', async (route) => {
      requests += 1;
      await route.abort();
    });
    await page.route('**/api/v1/destinations', async (route) => {
      destinationRequests += 1;
      await route.fulfill({ json: { destinations: [{ destination: 'Hội An', productCount: 15 }] } });
    });
    await page.goto('/');
    // Home tự tải điểm đến khi khối "Bạn muốn đi đâu?" tới gần vùng nhìn; điều cần kiểm là việc mở widget không tải thêm.
    await page.waitForLoadState('networkidle');
    destinationRequests = 0;
    await page.getByRole('button', { name: 'Mở trợ lý du lịch AI' }).click();
    const dialog = page.getByRole('dialog', { name: 'Trợ lý du lịch AI' });
    const input = dialog.getByPlaceholder(openingPlaceholder);
    await expect(dialog.getByRole('heading', { name: 'Bạn muốn đi đâu tiếp theo?' })).toBeVisible();
    await expect(input).toBeFocused();
    await expect(dialog.getByRole('textbox')).toHaveCount(1);
    await expect(dialog.getByRole('button', { name: 'Gửi yêu cầu' })).toBeDisabled();
    await dialog.getByRole('button', { name: 'Nghỉ dưỡng', exact: true }).click();
    await expect(input).toHaveValue(/nghỉ dưỡng/);
    await expect(dialog.getByRole('button', { name: 'Gửi yêu cầu' })).toBeEnabled();
    expect(requests).toBe(0);
    expect(destinationRequests).toBe(0);
    await dialog.screenshot({ path: `/tmp/travel-ai-opening-${width}.png`, animations: 'disabled' });

    await dialog.getByRole('button', { name: 'Thêm thông tin chuyến đi' }).click();
    await expect(dialog.getByRole('button', { name: 'Hội An', exact: true })).toBeVisible();
    await expect(dialog.getByRole('button', { name: 'Thêm thông tin chuyến đi' })).toHaveAttribute('aria-expanded', 'true');
    const geometry = await input.evaluate((element) => {
      const box = element.getBoundingClientRect();
      return { left: box.left, right: box.right, viewport: window.innerWidth };
    });
    expect(geometry.left).toBeGreaterThanOrEqual(0);
    expect(geometry.right).toBeLessThanOrEqual(geometry.viewport);
    await dialog.getByRole('button', { name: 'Thêm thông tin chuyến đi' }).click();
    await dialog.getByRole('button', { name: 'Mở rộng toàn màn hình' }).click();
    await expect(dialog.getByPlaceholder(openingPlaceholder)).toHaveValue(/nghỉ dưỡng/);
    await dialog.getByRole('button', { name: 'Đóng', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Mở trợ lý du lịch AI' })).toBeFocused();
    expect(requests).toBe(0);
    expect(errors).toEqual([]);
  });
}

test('keyboard submission switches to chat, preserves context, and resets to the opening', async ({ page }) => {
  const payloads: Array<Record<string, unknown>> = [];
  await page.route('**/api/v1/assistant/itineraries/stream', async (route) => {
    payloads.push(route.request().postDataJSON());
    const response = payloads.length === 1
      ? { status: 'NEEDS_CLARIFICATION', conversationId: 'opening-session', question: 'Bạn muốn đi ngày nào?', missingFields: ['startDate'] }
      : { status: 'NO_RESULTS', conversationId: 'opening-session', message: 'Chưa tìm thấy kết quả phù hợp.', suggestions: [] };
    await route.fulfill({ contentType: 'text/event-stream', body: `event: run.completed\ndata: ${JSON.stringify({ response })}\n\n` });
  });
  await page.goto('/');
  await page.getByRole('button', { name: 'Mở trợ lý du lịch AI' }).click();
  const dialog = page.getByRole('dialog', { name: 'Trợ lý du lịch AI' });
  const input = dialog.getByRole('textbox');
  await input.fill('Đi Hội An 3 ngày');
  await input.press('Shift+Enter');
  await expect(input).toHaveValue('Đi Hội An 3 ngày\n');
  expect(payloads).toHaveLength(0);
  await input.press('Enter');
  await expect(dialog.getByText('Bạn muốn đi ngày nào?')).toBeVisible();
  await expect(dialog.getByRole('textbox')).toHaveCount(1);
  await expect(dialog.getByRole('heading', { name: 'Bạn muốn đi đâu tiếp theo?' })).toHaveCount(0);
  await expect(dialog.getByRole('textbox')).toBeFocused();
  await dialog.getByRole('textbox').fill('Ngày 15/10, 2 người');
  await dialog.getByRole('button', { name: 'Gửi yêu cầu' }).click();
  await expect(dialog.getByText('Chưa tìm thấy kết quả phù hợp.')).toBeVisible();
  expect(payloads).toHaveLength(2);
  expect(payloads[0]).toMatchObject({ message: 'Đi Hội An 3 ngày', conversationId: null });
  expect(payloads[1]).toMatchObject({ message: 'Ngày 15/10, 2 người', conversationId: 'opening-session' });
  await dialog.getByRole('button', { name: 'Danh sách hội thoại & Tạo chat mới' }).click();
  await dialog.getByRole('button', { name: 'Đoạn chat mới' }).click();
  await expect(dialog.getByPlaceholder(openingPlaceholder)).toHaveValue('');
  await expect(dialog.getByRole('heading', { name: 'Bạn muốn đi đâu tiếp theo?' })).toBeVisible();
  await expect(dialog.getByRole('textbox')).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await expect(dialog.getByRole('button', { name: 'Đóng', exact: true })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: 'Mở trợ lý du lịch AI' })).toBeFocused();
});

test('completed results still open the timeline and map after the widget split', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.route('**/api/v1/assistant/itineraries/stream', async (route) => {
    await route.fulfill({ contentType: 'text/event-stream', body: `event: run.completed\ndata: ${JSON.stringify({ response: completed })}\n\n` });
  });
  await page.route('**/*.tile.openstreetmap.org/**', (route) => route.abort());
  await page.route('**/router.project-osrm.org/**', (route) => route.abort());
  await page.goto('/');
  await page.getByRole('button', { name: 'Mở trợ lý du lịch AI' }).click();
  await page.getByPlaceholder(openingPlaceholder).fill('Lập lịch trình Nha Trang 3 ngày');
  await page.getByRole('button', { name: 'Gửi yêu cầu' }).click();
  await page.getByRole('button', { name: 'Xem lộ trình & Bản đồ song song' }).click();
  const plan = page.getByRole('region', { name: 'Lịch trình theo ngày' });
  await expect(plan.getByRole('heading', { name: completed.itinerary.title, exact: true })).toBeVisible();
  await expect(plan.getByRole('button', { name: 'Tất cả', exact: true })).toBeVisible();
  await plan.getByRole('button', { name: 'Ngày 1', exact: true }).click();
  await expect(page.getByRole('button', { name: 'Thanh toán tất cả', exact: true })).toHaveCount(0);
  await expect(page.getByRole('dialog', { name: 'Trợ lý du lịch AI' }).getByRole('textbox')).toHaveCount(1);
  expect(errors).toEqual([]);
});

for (const width of [390,1024]) {
  test(`progress and preview follow the stream at ${width}px`, async ({page}) => {
    const {default:events}=await import('../../../shared/mocks/itinerary-agent/stream-plan.json',{with:{type:'json'}});
    await page.setViewportSize({width,height:900});
    await page.addInitScript((frames) => {
      const original=window.fetch;
      window.fetch=async (input,init) => {
        if (String(input).includes('/assistant/itineraries/stream')) {
          const encoder=new TextEncoder();
          return new Response(new ReadableStream({start(controller) {
            frames.forEach((frame,index) => {
              const send = () => {
                controller.enqueue(encoder.encode(`event: ${frame.event}\ndata: ${JSON.stringify(frame.data)}\n\n`));
                if (index===frames.length-1) controller.close();
              };
              if (index===frames.length-1) window.addEventListener('finish-progress-fixture',send,{once:true});
              else window.setTimeout(send,index*300);
            });
          }}),{headers:{'Content-Type':'text/event-stream'}});
        }
        return original(input,init);
      };
    },events);
    await page.goto('/');
    await page.getByRole('button',{name:'Mở trợ lý du lịch AI'}).click();
    const dialog=page.getByRole('dialog',{name:'Trợ lý du lịch AI'});
    await dialog.getByPlaceholder(openingPlaceholder).fill('Lập lịch trình Nha Trang');
    await dialog.getByRole('button',{name:'Gửi yêu cầu'}).click();
    await expect(dialog.getByText(/tìm thấy 10/)).toBeVisible();
    const preview=dialog.getByRole('region',{name:'Sản phẩm đã chọn'});
    await expect(preview).toBeVisible({timeout:7000});
    await expect(preview.getByRole('button',{name:/Thêm|Đặt ngay/})).toHaveCount(0);
    await dialog.screenshot({path:`/tmp/travel-agent-progress-${width}.png`,animations:'disabled'});
    const overflow=await dialog.evaluate((el)=>el.scrollWidth>el.clientWidth);
    expect(overflow).toBe(false);
    await page.evaluate(() => window.dispatchEvent(new Event('finish-progress-fixture')));
    await expect(dialog.getByRole('button',{name:/Xem các bước/})).toBeVisible({timeout:5000});
    await expect(preview).toHaveCount(0);
    await dialog.getByRole('button',{name:/Xem các bước/}).click();
    await expect(dialog.getByRole('button',{name:/Thu gọn/})).toHaveAttribute('aria-expanded','true');
  });
}

test('progress explains the current Hue request across turns without repeating a saved trip',async({page})=>{
  const {default:fixture}=await import('../../../shared/mocks/itinerary-agent/stream-explore-jobs.json',{with:{type:'json'}});
  let turn=0;
  await page.setViewportSize({width:390,height:900});
  await page.route('**/api/v1/assistant/itineraries/stream',async(route)=>{
    turn+=1;
    const frames=structuredClone(fixture) as Array<{event:string;data:Record<string,unknown>}>;
    for(const frame of frames){
      const p=frame.data.progress as Record<string,unknown>|undefined;
      if(!p) continue;
      const groups=(p.searches ?? []) as Array<{groupId:string;kind:'hotel'|'attraction';scope:Record<string,unknown>}>;
      for(const group of groups){group.scope={destination:'Huế',intent:turn>1 ? 'more':'new'};if(group.groupId==='job:1')group.kind='attraction';}
      for(const notice of (p.notices ?? []) as Array<{groupId?:string;kind?:string}>) if(notice.groupId==='job:1') notice.kind='attraction';
      if(frame.data.nodeId==='orchestrate' || groups.length){
        p.understood={intent:{destination:'Nha Trang',startDate:'2026-10-17',origin:'Nghệ An'},
          jobs:[{groupId:'job:1',kind:'attraction',scope:{destination:'Huế',intent:turn>1?'more':'new'}},
            {groupId:'job:2',kind:'hotel',scope:{destination:'Huế',intent:turn>1?'more':'new'}}]};
      }
    }
    await route.fulfill({contentType:'text/event-stream',body:frames.map((f)=>`event: ${f.event}\ndata: ${JSON.stringify(f.data)}\n\n`).join('')});
  });
  await page.goto('/');
  await page.getByRole('button',{name:'Mở trợ lý du lịch AI'}).click();
  const dialog=page.getByRole('dialog',{name:'Trợ lý du lịch AI'});
  await dialog.getByPlaceholder(openingPlaceholder).fill('Huế có gì chơi?');
  await dialog.getByRole('button',{name:'Gửi yêu cầu'}).click();
  await dialog.getByRole('button',{name:/Xem các bước/}).click();
  await expect(dialog.getByText(/Bạn đang tìm điểm tham quan ở Huế/)).toBeVisible();
  await expect(dialog.getByText(/Nha Trang|17\/10|Nghệ An/)).toHaveCount(0);
  await dialog.getByRole('textbox').fill('Cho mình thêm gợi ý ở Huế');
  await dialog.getByRole('button',{name:'Gửi yêu cầu'}).click();
  await dialog.getByRole('button',{name:/Xem các bước/}).last().click();
  await expect(dialog.getByText(/Bạn muốn xem thêm điểm tham quan ở Huế/)).toBeVisible();
  await expect(dialog.getByText(/Nha Trang|17\/10|Nghệ An/)).toHaveCount(0);
  await dialog.screenshot({path:'/tmp/travel-progress-hue-current-turn.png',animations:'disabled'});
});

import express from 'express';
import { GoogleGenAI } from '@google/genai';
import { MemorySharedTripStore } from './stores/memory-shared-trip-store';
import { registerHealthRoutes } from './routes/health';
import { registerTripRoutes } from './routes/trips';

const PORT = Number(process.env.PORT || 3001);

function getGeminiClient(): GoogleGenAI | null {
  const apiKey = process.env.GEMINI_API_KEY;
  if (!apiKey || apiKey === 'MY_GEMINI_API_KEY' || apiKey === 'undefined') {
    return null;
  }
  return new GoogleGenAI({
    apiKey,
    httpOptions: {
      headers: {
        'User-Agent': 'aistudio-build',
      },
    },
  });
}

// System instructions tailored to specific chatbot roles
const SYSTEM_INSTRUCTIONS = {
  general: `Bạn là Trợ lý Du lịch Thông minh V-OTA tại Việt Nam.
Vai trò của bạn là người đồng hành đáng tin cậy, giải đáp mọi thắc mắc du lịch về các điểm đến (Nha Trang, Phú Quốc, Đà Nẵng, Hạ Long, Hội An, Hà Nội...), khách sạn, resort, vé tham quan và hoạt động giải trí.
Phong cách giao tiếp: Thân thiện, chu đáo, chuyên nghiệp và định dạng Markdown rõ ràng với gạch đầu dòng và in đậm các từ khóa quan trọng. Luôn đề xuất 2-3 câu hỏi gợi ý tiếp theo phù hợp dạng danh sách [Gợi ý 1 | Gợi ý 2].`,

  itinerary: `Bạn là Chuyên gia Thiết kế Lịch trình Du lịch V-OTA (Itinerary Specialist).
Vai trò của bạn là phân bổ thời gian tối ưu theo từng buổi (Sáng - Trưa - Chiều - Tối) cho các chuyến đi.
Quy tắc chuyên môn:
1. Tránh ánh nắng gắt buổi trưa cho các gia đình có trẻ nhỏ và người lớn tuổi.
2. Sắp xếp các điểm dừng gần nhau theo cụm địa lý để giảm thời gian di chuyển.
3. Kết hợp hài hòa giữa các điểm vui chơi năng động (công viên nước, Safari, cáp treo) và thời gian nghỉ ngơi thư giãn.
Định dạng câu trả lời: Rõ ràng, chia theo mốc thời gian hoặc từng ngày cụ thể, gợi ý phương tiện di chuyển phù hợp.`,

  culinary: `Bạn là Chuyên gia Ẩm thực & Văn hóa Bản địa V-OTA (Local Culinary & Culture Guide).
Vai trò của bạn là hướng dẫn du khách khám phá những món ăn đặc sản ngon chuẩn vị nhất, các khu chợ đêm ẩm thực nổi tiếng và những nét văn hóa đặc sắc tại địa phương (ví dụ: bún quậy Kiến Xây ở Phú Quốc, nem nướng Đặng Văn Quyên ở Nha Trang, bánh tráng cuốn thịt heo Đà Nẵng, chả mực Bãi Cháy...).
Phong cách: Sôi nổi, truyền cảm hứng, hướng dẫn cách ăn đúng điệu và lưu ý về giá cả, thời gian mở cửa của quán.`,

  budget: `Bạn là Chuyên gia Tối ưu Ngân sách & Săn Deal V-OTA (Budget & Deal Hunter).
Vai trò của bạn là giúp du khách có một chuyến đi tuyệt vời với chi phí tối ưu và tiết kiệm nhất.
Quy tắc chuyên môn:
1. Đề xuất đặt các gói combo phòng + vé tham quan để tiết kiệm 15-25% so với mua lẻ.
2. Phân tích bảng dự toán chi phí minh bạch (chỗ ở, vé tham quan, ăn uống, di chuyển).
3. Gợi ý các mẹo du lịch tiết kiệm: đi lại bằng xe buýt điện/shuttle bus miễn phí của resort, khung giờ khuyến mãi và các điểm tham quan miễn phí đẹp.`
};

const LOCALE_METADATA: Record<string, { name: string; nativeName: string }> = {
  vi: { name: 'Vietnamese', nativeName: 'Tiếng Việt' },
  en: { name: 'English', nativeName: 'English' },
  fr: { name: 'French', nativeName: 'Français' },
  ja: { name: 'Japanese', nativeName: '日本語' },
  ko: { name: 'Korean', nativeName: '한국어' },
  zh: { name: 'Chinese', nativeName: '中文' },
  de: { name: 'German', nativeName: 'Deutsch' },
  es: { name: 'Spanish', nativeName: 'Español' },
  ru: { name: 'Russian', nativeName: 'Русский' },
  th: { name: 'Thai', nativeName: 'ไทย' }
};

export function createApiApp() {
  const app = express();
  app.use(express.json());
  const sharedTripsStore = new MemorySharedTripStore();

  registerHealthRoutes(app);

  // Multi-turn Gemini Chatbot Endpoint
  app.post('/api/assistant/chat', async (req, res) => {
    try {
      const { 
        message, 
        history = [], 
        role = 'general', 
        model = 'auto', 
        locale = 'vi',
        context = {} 
      } = req.body;

      if (!message || typeof message !== 'string') {
        return res.status(400).json({ error: 'Message is required' });
      }

      const targetLang = LOCALE_METADATA[locale] || LOCALE_METADATA.vi;

      // Model Selection Logic adhering to instructions:
      // - gemini-3.1-pro-preview: particularly complex tasks (detailed multi-day budget breakdown, in-depth logistics)
      // - gemini-3.5-flash: general tasks (default)
      // - gemini-3.1-flash-lite: tasks that should happen fast (quick Q&A, packing checklist, weather/food quick tips)
      let selectedModel = 'gemini-3.5-flash';
      if (model === 'gemini-3.1-pro-preview' || model === 'gemini-3.1-flash-lite' || model === 'gemini-3.5-flash') {
        selectedModel = model;
      } else {
        // Auto detection based on prompt complexity
        const lower = message.toLowerCase();
        const isComplex = lower.includes('tối ưu ngân sách') || 
                          lower.includes('bảng chi phí') || 
                          lower.includes('so sánh chi tiết') || 
                          lower.includes('kế hoạch 5 ngày') || 
                          lower.includes('nhiều điểm đến') ||
                          lower.includes('lập dự toán') ||
                          lower.includes('budget breakdown') ||
                          lower.includes('detailed itinerary') ||
                          lower.includes('cost comparison');

        const isFast = lower.length < 35 || 
                       lower.includes('mặc gì') || 
                       lower.includes('thời tiết') || 
                       lower.includes('check-in') || 
                       lower.includes('mấy giờ') || 
                       lower.includes('nhanh') ||
                       lower.includes('weather') ||
                       lower.includes('quick tip');

        if (isComplex) {
          selectedModel = 'gemini-3.1-pro-preview';
        } else if (isFast) {
          selectedModel = 'gemini-3.1-flash-lite';
        } else {
          selectedModel = 'gemini-3.5-flash';
        }
      }

      // Build contextual system instruction with language enforcement
      const baseSystemPrompt = SYSTEM_INSTRUCTIONS[role as keyof typeof SYSTEM_INSTRUCTIONS] || SYSTEM_INSTRUCTIONS.general;
      const contextAddition = `
Ngữ cảnh chuyến đi hiện tại của người dùng:
- Điểm đến đang xem: ${context.destination || 'Nha Trang'}
- Số ngày dự kiến: ${context.days || 3} ngày
- Đối tượng: ${context.party === 'family_with_kids' ? 'Gia đình có trẻ nhỏ' : 'Cặp đôi/bạn bè'}
- Chuyến đi đã tạo tiêu đề: ${context.activePlanTitle || 'Chưa lưu'}

CRITICAL LANGUAGE MANDATE:
The user has requested the interaction in ${targetLang.nativeName} (${targetLang.name}).
You MUST write your entire response, recommendations, advice, tone, and the suggested follow-up questions at the very end in brackets [Follow-up 1 | Follow-up 2 | Follow-up 3] strictly in ${targetLang.name} (${targetLang.nativeName}).
Make sure all place recommendations, itinerary slots, and practical travel tips are rendered naturally in ${targetLang.name}.`;

      const finalSystemInstruction = `${baseSystemPrompt}\n${contextAddition}`;

      const ai = getGeminiClient();

      if (ai) {
        try {
          // Format multi-turn conversation contents
          const formattedContents = [];

          // Add history turns if available
          if (Array.isArray(history) && history.length > 0) {
            for (const item of history) {
              if (item.text && item.role) {
                formattedContents.push({
                  role: item.role === 'model' || item.role === 'assistant' ? 'model' : 'user',
                  parts: [{ text: item.text }],
                });
              }
            }
          }

          // Add current message
          formattedContents.push({
            role: 'user',
            parts: [{ text: message }],
          });

          const response = await ai.models.generateContent({
            model: selectedModel,
            contents: formattedContents,
            config: {
              systemInstruction: finalSystemInstruction,
              temperature: 0.7,
            },
          });

          const rawText = response.text || '';
          
          // Extract suggested follow-ups if included
          const followUps: string[] = [];
          const suggestionMatch = rawText.match(/\[(.*?)\]/);
          if (suggestionMatch && suggestionMatch[1]) {
            suggestionMatch[1].split('|').forEach(s => {
              const clean = s.trim();
              if (clean) followUps.push(clean);
            });
          }

          // Clean up reply text
          const cleanedText = rawText.replace(/\[.*?\|.*?\]/g, '').trim();

          // Detect potential intent updates (destination, days)
          let detectedIntent: any = null;
          const lowerMsg = message.toLowerCase();
          const destinations = ['Nha Trang', 'Phú Quốc', 'Đà Nẵng', 'Hạ Long', 'Hội An', 'Hà Nội'];
          for (const d of destinations) {
            if (lowerMsg.includes(d.toLowerCase()) || 
                (d === 'Phú Quốc' && lowerMsg.includes('phu quoc')) ||
                (d === 'Đà Nẵng' && lowerMsg.includes('da nang')) ||
                (d === 'Hội An' && lowerMsg.includes('hoi an')) ||
                (d === 'Hạ Long' && lowerMsg.includes('ha long')) ||
                (d === 'Hà Nội' && lowerMsg.includes('hanoi')) ||
                (d === 'Nha Trang' && lowerMsg.includes('nhatrang'))) {
              detectedIntent = { destination: d };
              break;
            }
          }
          const daysMatch = lowerMsg.match(/(\d+)\s*(ngày|hôm|day|days|jour|tage|dias)/);
          if (daysMatch) {
            detectedIntent = { ...(detectedIntent || {}), days: parseInt(daysMatch[1], 10) };
          }
          if (lowerMsg.includes('gia đình') || lowerMsg.includes('trẻ em') || lowerMsg.includes('family') || lowerMsg.includes('kids')) {
            detectedIntent = { ...(detectedIntent || {}), party: 'family_with_kids' };
          } else if (lowerMsg.includes('cặp đôi') || lowerMsg.includes('người yêu') || lowerMsg.includes('couple') || lowerMsg.includes('romantic')) {
            detectedIntent = { ...(detectedIntent || {}), party: 'couple' };
          }

          const defaultFollowUpsByLocale: Record<string, string[]> = {
            vi: ['Tối ưu lại lịch trình cho phù hợp', 'Gợi ý thêm đặc sản ẩm thực', 'Chi phí dự tính là bao nhiêu?'],
            en: ['Optimize itinerary for our family', 'Recommend authentic local food', 'What is the estimated total cost?'],
            fr: ['Optimiser l\'itinéraire pour notre groupe', 'Recommander des spécialités locales', 'Quel est le coût total estimé ?'],
            ja: ['家族向けに旅程を再調整する', '地元の名物グルメを提案して', '3日間の概算費用はいくら？'],
            ko: ['가족 여행에 맞게 일정 최적화하기', '현지 대표 맛집 추천해줘', '예상 경비는 얼마인가요?'],
            zh: ['为我们优化专属行程', '推荐地道特色美食', '预计总花费大概多少？'],
            de: ['Reiseplan für uns optimieren', 'Lokale Spezialitäten empfehlen', 'Wie hoch sind die geschätzten Gesamtkosten?'],
            es: ['Optimizar el itinerario para nuestro viaje', 'Recomendar comida típica local', '¿Cuál es el coste total estimado?'],
            ru: ['Оптимизировать маршрут для поездки', 'Посоветовать местные деликатесы', 'Каков ориентировочный бюджет?'],
            th: ['ปรับแต่งแผนเที่ยวให้ลงตัวยิ่งขึ้น', 'แนะนำอาหารพื้นเมืองรสเด็ด', 'ค่าใช้จ่ายโดยประมาณเท่าไหร่?']
          };

          return res.json({
            success: true,
            reply: cleanedText || rawText,
            modelUsed: selectedModel,
            role,
            suggestedFollowUps: followUps.length > 0 ? followUps : (defaultFollowUpsByLocale[locale] || defaultFollowUpsByLocale.en),
            detectedIntent,
            source: 'gemini-api'
          });
        } catch (apiErr: any) {
          console.warn('Gemini generateContent error, falling back to rule-based conversation engine:', apiErr?.message);
        }
      }

      // Offline / Fallback multi-turn response engine with multilingual support
      const dest = context.destination || 'Nha Trang';
      let fallbackReply = '';
      let fallbackFollowUps: string[] = [];

      if (locale === 'en') {
        fallbackFollowUps = [
          `Best local food in ${dest}`,
          `Family-friendly schedule for ${dest}`,
          `Estimated budget breakdown`
        ];
        if (role === 'culinary') {
          fallbackReply = `Here are some of the most celebrated culinary specialties in **${dest}** you should not miss:\n\n` +
            `- **Main Dishes:** Fresh seafood at the local pier, char-grilled seafood platters, and authentic regional noodles.\n` +
            `- **Street Food & Night Markets:** Explore the bustling night market for traditional desserts, grilled skewers, and tropical smoothies.\n` +
            `- **Dining Tip:** Visit around 6:30 PM - 8:00 PM for the freshest catch of the day!`;
        } else if (role === 'budget') {
          fallbackReply = `To optimize your travel budget for **${dest}**:\n\n` +
            `1. **Book Bundled Combos:** Save 15% - 20% by booking hotel stays bundled with theme park tickets or island tours.\n` +
            `2. **Advance Online Booking:** Book online through V-OTA to skip ticket lines and unlock exclusive rates.\n` +
            `3. **Transportation:** Take advantage of complimentary resort shuttles or eco-friendly electric vehicles.`;
        } else if (role === 'itinerary') {
          fallbackReply = `Suggested itinerary coordination for **${dest}**:\n\n` +
            `- **Morning:** Outdoor activities, island-hopping, or cable car rides while the morning breeze is pleasant.\n` +
            `- **Noon:** Enjoy a coastal lunch featuring regional seafood, followed by a midday break to avoid direct sun.\n` +
            `- **Afternoon & Evening:** Relaxing beach strolls, golden hour sunsets, and evening light & water shows.`;
        } else {
          fallbackReply = `Hello! For your trip to **${dest}** (${context.days || 3} days), I have prepared top-tier resort hotels and verified attraction tickets in the V-OTA catalog.\n\nFeel free to ask me to adjust days, add dining spots, or provide a 5-day weather forecast anytime!`;
        }
      } else if (locale === 'fr') {
        fallbackFollowUps = [
          `Meilleurs restaurants à ${dest}`,
          `Itinéraire pour famille à ${dest}`,
          `Estimation du budget voyage`
        ];
        fallbackReply = `Bonjour ! Pour votre voyage à **${dest}** (${context.days || 3} jours), j'ai préparé une sélection exclusive d'hôtels et d'activités vérifiées sur V-OTA.\n\nN'hésitez pas à me demander d'ajuster le nombre de jours, d'ajouter des restaurants typiques ou d'optimiser votre budget !`;
      } else if (locale === 'ja') {
        fallbackFollowUps = [
          `${dest}のおすすめグルメ`,
          `${dest}の家族向けプラン`,
          `旅行費用の見積もり`
        ];
        fallbackReply = `こんにちは！**${dest}**へのご旅行（${context.days || 3}日間）に向けて、V-OTAで予約可能な厳選ホテルや観光ツアーをご用意しました。\n\n日数の調整やおすすめレストラン、予算の最適化など、いつでも気軽にご相談ください！`;
      } else if (locale === 'ko') {
        fallbackFollowUps = [
          `${dest} 대표 맛집 추천`,
          `${dest} 가족 맞춤 여행 코스`,
          `예상 여행 경비 내역`
        ];
        fallbackReply = `안녕하세요! **${dest}** 여행(${context.days || 3}일 일정)을 위해 V-OTA에서 즉시 예약 가능한 리조트와 액티비티를 맞춤형으로 준비했습니다.\n\n일정 조정이나 로컬 맛집, 예산 견적이 필요하시면 언제든 말씀해 주세요!`;
      } else if (locale === 'zh') {
        fallbackFollowUps = [
          `${dest} 必吃特色美食`,
          `${dest} 亲子家庭行程方案`,
          `行程花费预算明细`
        ];
        fallbackReply = `您好！针对您的 **${dest}** ${context.days || 3} 天之旅，我已为您匹配了 V-OTA 平台的精选度假酒店与游玩门票。\n\n您可以随时让我调整行程天数、推荐地道餐厅或生成费用预算清单！`;
      } else {
        // Default Vietnamese
        fallbackFollowUps = [
          `Gợi ý món ăn ngon ở ${dest}`,
          `Lịch trình phù hợp cho gia đình tại ${dest}`,
          `Bảng chi phí ước tính chuyến đi`
        ];
        if (role === 'culinary') {
          fallbackReply = `Dưới đây là một số đặc sản trứ danh tại **${dest}** mà bạn không nên bỏ lỡ:\n\n` +
            `- **Món chính:** Hải sản tươi sống tại khu vực bến tàu, các món nướng và bún đặc sản địa phương.\n` +
            `- **Ăn vặt & Chợ đêm:** Khám phá khu chợ đêm nhộn nhịp, chè truyền thống và các loại sinh tố nhiệt đới.\n` +
            `- **Mẹo thưởng thức:** Nên đi ăn vào khoảng 18h30 - 20h00 để có hải sản tươi ngon nhất trong ngày!`;
        } else if (role === 'budget') {
          fallbackReply = `Để tối ưu ngân sách cho chuyến đi **${dest}**:\n\n` +
            `1. **Đặt gói Combo:** Tiết kiệm từ 15% - 20% khi chọn combo khách sạn 5 sao kèm vé VinWonders / Tour đảo.\n` +
            `2. **Thời điểm tham quan:** Đặt vé trực tuyến trước để tránh xếp hàng và hưởng ưu đãi giá độc quyền trên V-OTA.\n` +
            `3. **Di chuyển:** Sử dụng dịch vụ đưa đón của khách sạn hoặc xe buýt du lịch tiện lợi.`;
        } else if (role === 'itinerary') {
          fallbackReply = `Gợi ý điều phối lịch trình cho **${dest}**:\n\n` +
            `- **Buổi sáng:** Tham gia các hoạt động ngoài trời, tour đảo hoặc cáp treo khi thời tiết còn mát mẻ và biển êm.\n` +
            `- **Buổi trưa:** Thưởng thức bữa trưa đặc sản tại nhà hàng ven biển, sau đó nghỉ ngơi tại phòng để tránh nắng gắt.\n` +
            `- **Buổi chiều & Tối:** Tắm biển thư giãn, ngắm hoàng hôn và xem các show trình diễn nghệ thuật ánh sáng đặc sắc.`;
        } else {
          fallbackReply = `Chào bạn! Với chuyến đi **${dest}** (${context.days || 3} ngày), mình đã chuẩn bị sẵn các lựa chọn khách sạn nghỉ dưỡng và vé tham quan tối ưu trong kho V-OTA.\n\nBạn có thể yêu cầu mình điều chỉnh số ngày, bổ sung địa điểm ăn uống hoặc kiểm tra thời tiết 5 ngày tới bất cứ lúc nào!`;
        }
      }

      return res.json({
        success: true,
        reply: fallbackReply,
        modelUsed: selectedModel,
        role,
        suggestedFollowUps: fallbackFollowUps,
        source: 'v-ota-fallback-assistant'
      });
    } catch (error: any) {
      console.error('Server error in /api/assistant/chat:', error);
      return res.status(500).json({ 
        error: 'Lỗi xử lý tin nhắn trợ lý', 
        details: error?.message 
      });
    }
  });

  // Assistant AI endpoint (Server-side Gemini API proxy with grounding fallback)
  app.post('/api/assistant/plan', async (req, res) => {
    const { prompt, destination, days, party, locale = 'vi' } = req.body;
    const targetLang = LOCALE_METADATA[locale] || LOCALE_METADATA.vi;

    const ai = getGeminiClient();
    if (ai) {
      try {
        const response = await ai.models.generateContent({
          model: 'gemini-3.5-flash',
          contents: `You are the V-OTA AI travel assistant in Vietnam. User request: "${prompt}". Destination: "${destination || 'Nha Trang'}", ${days || 3} days, party: "${party || 'family with kids'}".
Please provide a concise 2-3 sentence personalized travel advice and timing recommendation, written strictly in ${targetLang.name} (${targetLang.nativeName}).`
        });

        return res.json({
          success: true,
          aiNarrative: response.text,
          source: 'gemini-3.5-flash'
        });
      } catch (err: any) {
        console.warn('Gemini API call warning, falling back to local grounded narrative:', err?.message);
      }
    }

    // Resilient fallback narrative based on locale
    const fallbackNarratives: Record<string, string> = {
      vi: `Lịch trình được tối ưu hóa cho điểm đến ${destination || 'Nha Trang'} với sự cân bằng giữa trải nghiệm vui chơi công viên giải trí và nghỉ ngơi thư giãn ven biển.`,
      en: `The itinerary is carefully optimized for ${destination || 'Nha Trang'}, striking the ideal balance between amusement parks and tranquil beachside relaxation.`,
      fr: `L'itinéraire est parfaitement optimisé pour ${destination || 'Nha Trang'}, alliant parcs d'attractions et détente en bord de mer.`,
      ja: `${destination || 'ニャチャン'}を満喫できるよう、テーマパークと静かなビーチリゾートでの休暇をバランスよく最適化した旅程です。`,
      ko: `${destination || '나트랑'}의 테마파크 액티비티와 해변 힐링 휴식이 완벽한 균형을 이루도록 설계된 맞춤형 일정입니다.`,
      zh: `该行程针对 ${destination || '芽庄'} 进行了精心优化，兼顾了主题乐园的精彩体验与海滨度假的悠闲放松。`,
      de: `Der Reiseplan für ${destination || 'Nha Trang'} bietet die ideale Balance aus Erlebnisparks und erholsamen Strandtagen.`,
      es: `El itinerario está optimizado para ${destination || 'Nha Trang'}, combinando parques de diversiones y relajación en la playa.`,
      ru: `Маршрут для ${destination || 'Нячанга'} гармонично сочетает активные развлечения в парках и спокойный пляжный отдых.`,
      th: `แผนการเดินทางสำหรับ ${destination || 'ญาจาง'} จัดสรรอย่างลงตัวระหว่างสวนสนุกสุดมันส์และการพักผ่อนริมชายหาดอันเงียบสงบ`
    };

    return res.json({
      success: true,
      aiNarrative: fallbackNarratives[locale] || fallbackNarratives.en,
      source: 'v-ota-grounded-engine'
    });
  });

  registerTripRoutes(app, sharedTripsStore);

  return app;
}

export function startServer() {
  const app = createApiApp();
  app.listen(PORT, '0.0.0.0', () => {
    console.log(`V-OTA API Server running on http://0.0.0.0:${PORT}`);
  });
}

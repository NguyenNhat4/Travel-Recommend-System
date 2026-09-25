import { SupportedLocale, SUPPORTED_LOCALES } from '../types/locale';
import { GroundedPlan, AgentRole, ItinerarySlot } from '../types/travel';

export interface AssistantTranslations {
  assistantTitle: string;
  assistantSubtitle: string;
  headerBadge: string;
  inputPlaceholder: string;
  sendButton: string;
  voiceListening: string;
  voiceListeningTooltip: string;
  clearChat: string;
  itineraryTab: string;
  mapViewTab: string;
  listViewTab: string;
  dayTabPrefix: string;
  totalEstimated: string;
  bookableServices: string;
  addToCartAll: string;
  saveTrip: string;
  savedTrip: string;
  shareTrip: string;
  timeSlots: {
    morning: string;
    noon: string;
    afternoon: string;
    evening: string;
  };
  roles: Record<AgentRole, {
    label: string;
    desc: string;
    welcomeMsg: string;
    suggestedFollowUps: string[];
  }>;
  welcomeIntro: (name: string) => string;
  sharedTripWelcome: (sender: string, title: string, days: number, count: number) => string;

  // Component convenience aliases & helpers
  day?: (d: number) => string;
  aiAssistantTitle?: string;
  aiAssistantSubtitle?: string;
  send?: string;
  saved?: string;
  savedTrips?: string;
  share?: string;
  listView?: string;
  mapView?: string;
  stayEntireTrip?: string;
  viewRoute?: string;
  morning?: string;
  noon?: string;
  afternoon?: string;
  evening?: string;
  estimated?: string;
  addAllToCart?: string;
  locatedCoordinates?: string;
  processing?: string;
  step1?: string;
  step2?: string;
  step3?: string;
  noPlanSelected?: string;
  noPlanHint?: string;
}

export const TRANSLATIONS: Record<SupportedLocale, AssistantTranslations> = {
  vi: {
    assistantTitle: 'Trợ lý lịch trình AI V-OTA',
    assistantSubtitle: 'Lên lịch trình thông minh với 100% dịch vụ thật, có giá niêm yết và thêm giỏ hàng trong 1 chạm.',
    headerBadge: 'AI Du lịch',
    inputPlaceholder: 'Hỏi bất kỳ điều gì: "3 ngày Nha Trang cho gia đình", "món ngon Phú Quốc", "khách sạn Hội An"...',
    sendButton: 'Gửi',
    voiceListening: 'Đang lắng nghe...',
    voiceListeningTooltip: 'Nói yêu cầu du lịch của bạn',
    clearChat: 'Làm mới hội thoại',
    itineraryTab: 'Chi tiết lịch trình',
    mapViewTab: 'Bản đồ lộ trình',
    listViewTab: 'Danh sách chi tiết',
    dayTabPrefix: 'Ngày',
    totalEstimated: 'Tổng chi phí ước tính',
    bookableServices: 'dịch vụ đặt được',
    addToCartAll: 'Thêm tất cả vào giỏ',
    saveTrip: 'Lưu chuyến',
    savedTrip: 'Đã lưu',
    shareTrip: 'Chia sẻ',
    timeSlots: {
      morning: 'Buổi sáng',
      noon: 'Buổi trưa',
      afternoon: 'Buổi chiều',
      evening: 'Buổi tối'
    },
    roles: {
      general: {
        label: 'Toàn diện',
        desc: 'Tư vấn tổng quan, hỗ trợ điểm đến và mẹo du lịch',
        welcomeMsg: 'Chào bạn! Mình là Trợ lý Toàn diện V-OTA. Mình có thể giúp bạn giải đáp mọi thông tin chuyến đi, khách sạn và các dịch vụ du lịch tại Việt Nam.',
        suggestedFollowUps: ['3 ngày Nha Trang cho gia đình có trẻ nhỏ', 'Cuối tuần Phú Quốc 2 người', 'Khám phá Đà Nẵng 4 ngày']
      },
      itinerary: {
        label: 'Lịch trình',
        desc: 'Thiết kế lịch trình theo buổi (Sáng - Trưa - Chiều - Tối)',
        welcomeMsg: 'Chào bạn! Mình là Chuyên gia Thiết kế Lịch trình. Mình sẽ tối ưu hóa phân bổ thời gian từng buổi sáng, trưa, chiều, tối và lộ trình di chuyển hợp lý nhất.',
        suggestedFollowUps: ['Lịch trình tránh nắng cho trẻ nhỏ', 'Sắp xếp buổi tối đi đâu đẹp nhất?', 'Tour đảo buổi sáng kết hợp lặn ngắm san hô']
      },
      culinary: {
        label: 'Ẩm thực',
        desc: 'Món ngon đặc sản bản địa và địa chỉ quán ăn chuẩn vị',
        welcomeMsg: 'Chào bạn! Mình là Chuyên gia Ẩm thực & Văn hóa địa phương. Bạn muốn khám phá món ngon đặc sản hay quán ăn chuẩn vị nào?',
        suggestedFollowUps: ['Quán hải sản ngon nhất gần đây?', 'Đặc sản chợ đêm nên thử?', 'Món ăn sáng nổi tiếng địa phương?']
      },
      budget: {
        label: 'Ngân sách',
        desc: 'Tối ưu chi phí, săn combo tiết kiệm và dự toán',
        welcomeMsg: 'Chào bạn! Mình là Chuyên gia Tối ưu Ngân sách & Săn Deal. Mình sẽ giúp bạn tiết kiệm chi phí tối đa với combo ưu đãi và dự toán chi tiết!',
        suggestedFollowUps: ['Gợi ý combo tiết kiệm 20%?', 'Bảng dự toán chi phí 3 ngày?', 'Cách đi lại rẻ nhất tại điểm đến?']
      }
    },
    welcomeIntro: (name) => `Chào ${name}! Mình là Trợ lý Du lịch AI V-OTA. Bạn đang muốn lên kế hoạch đi đâu, mấy ngày và đi cùng ai? Hãy chia sẻ với mình nhé!`,
    sharedTripWelcome: (sender, title, days, count) => `Chào bạn! Bạn đang xem lịch trình "${title}" được chia sẻ bởi ${sender}. Lịch trình bao gồm ${days} ngày khám phá với ${count} dịch vụ đặt được ngay.`
  },

  en: {
    assistantTitle: 'V-OTA AI Travel Itinerary Assistant',
    assistantSubtitle: 'Smart itinerary planning with 100% real bookable services, transparent pricing, and 1-tap booking.',
    headerBadge: 'Travel AI',
    inputPlaceholder: 'Ask anything: "3 days in Nha Trang for family", "Phu Quoc seafood", "Hoi An boutique hotels"...',
    sendButton: 'Send',
    voiceListening: 'Listening...',
    voiceListeningTooltip: 'Speak your travel request',
    clearChat: 'Reset Chat',
    itineraryTab: 'Itinerary Details',
    mapViewTab: 'Route Map',
    listViewTab: 'Detailed List',
    dayTabPrefix: 'Day',
    totalEstimated: 'Estimated Total',
    bookableServices: 'bookable services',
    addToCartAll: 'Add All to Cart',
    saveTrip: 'Save Trip',
    savedTrip: 'Saved',
    shareTrip: 'Share',
    timeSlots: {
      morning: 'Morning',
      noon: 'Noon',
      afternoon: 'Afternoon',
      evening: 'Evening'
    },
    roles: {
      general: {
        label: 'General',
        desc: 'Comprehensive advice, destination highlights & travel tips',
        welcomeMsg: 'Hello! I am your V-OTA Comprehensive Travel Assistant. I can help you with trip planning, hotel recommendations, and activities across Vietnam.',
        suggestedFollowUps: ['3 days in Nha Trang for family with kids', 'Romantic weekend in Phu Quoc for couples', '4 days exploring Da Nang & Hoi An']
      },
      itinerary: {
        label: 'Itinerary',
        desc: 'Time slot coordination (Morning - Noon - Afternoon - Evening)',
        welcomeMsg: 'Hello! I am your Itinerary Design Specialist. I will optimize your daily timing, pacing, and convenient travel routes.',
        suggestedFollowUps: ['Sun-safe morning schedule for young kids', 'Best evening entertainment spots', 'Morning island hopping & snorkeling tour']
      },
      culinary: {
        label: 'Culinary',
        desc: 'Authentic local delicacies & curated restaurant spots',
        welcomeMsg: 'Hello! I am your Local Food & Culture Guide. Are you looking for authentic street food or top-rated seafood restaurants?',
        suggestedFollowUps: ['Best fresh seafood near the beach?', 'Must-try night market specialties?', 'Famous local breakfast spots?']
      },
      budget: {
        label: 'Budget',
        desc: 'Cost optimization, value combos & transparent breakdowns',
        welcomeMsg: 'Hello! I am your Budget & Deal Hunter. I will help you save money with discounted bundled combos and detailed expense estimates!',
        suggestedFollowUps: ['Suggest combos saving up to 20%?', 'Estimated 3-day budget breakdown?', 'Most cost-effective local transit?']
      }
    },
    welcomeIntro: (name) => `Hello ${name}! I am your V-OTA AI Travel Assistant. Where would you like to travel, for how many days, and with whom? Let me know!`,
    sharedTripWelcome: (sender, title, days, count) => `Hello! You are viewing the itinerary "${title}" shared by ${sender}. Featuring ${days} curated days with ${count} instantly bookable services.`
  },

  fr: {
    assistantTitle: 'Assistant de Voyage IA V-OTA',
    assistantSubtitle: 'Planification intelligente avec 100% de services réels réservables et prix transparents.',
    headerBadge: 'IA Voyage',
    inputPlaceholder: 'Demandez tout: "3 jours à Nha Trang en famille", "fruits de mer Phu Quoc"...',
    sendButton: 'Envoyer',
    voiceListening: 'À l\'écoute...',
    voiceListeningTooltip: 'Parlez de vos envies de voyage',
    clearChat: 'Réinitialiser',
    itineraryTab: 'Détails du séjour',
    mapViewTab: 'Carte de l\'itinéraire',
    listViewTab: 'Vue liste',
    dayTabPrefix: 'Jour',
    totalEstimated: 'Total estimé',
    bookableServices: 'services réservables',
    addToCartAll: 'Tout ajouter au panier',
    saveTrip: 'Enregistrer',
    savedTrip: 'Enregistré',
    shareTrip: 'Partager',
    timeSlots: {
      morning: 'Matin',
      noon: 'Midi',
      afternoon: 'Après-midi',
      evening: 'Soirée'
    },
    roles: {
      general: {
        label: 'Général',
        desc: 'Conseils complets, temps forts et astuces de voyage',
        welcomeMsg: 'Bonjour ! Je suis votre assistant de voyage V-OTA. Je peux vous guider pour vos séjours, hôtels et découvertes au Vietnam.',
        suggestedFollowUps: ['3 jours à Nha Trang en famille', 'Week-end en amoureux à Phu Quoc', 'Découvrir Da Nang et Hoi An en 4 jours']
      },
      itinerary: {
        label: 'Itinéraire',
        desc: 'Organisation par tranche horaire et trajets optimaux',
        welcomeMsg: 'Bonjour ! Je suis votre expert en conception d\'itinéraires. J\'optimise votre temps et vos déplacements au Vietnam.',
        suggestedFollowUps: ['Itinéraire matinal à l\'abri du soleil', 'Où sortir le soir en toute sécurité ?', 'Excursion matinale dans les îles']
      },
      culinary: {
        label: 'Gastronomie',
        desc: 'Spécialités locales authentiques et bonnes adresses',
        welcomeMsg: 'Bonjour ! Je suis votre guide culinaire local. Quels délices vietnamiens souhaitez-vous découvrir ?',
        suggestedFollowUps: ['Meilleurs fruits de mer frais ?', 'Spécialités incontournables du marché ?', 'Petits-déjeuners traditionnels ?']
      },
      budget: {
        label: 'Budget',
        desc: 'Optimisation des coûts et meilleures offres combinées',
        welcomeMsg: 'Bonjour ! Je suis votre conseiller budget. Économisons sur votre voyage avec des forfaits avantageux !',
        suggestedFollowUps: ['Offres combinées avec -20% ?', 'Estimation des dépenses sur 3 jours ?', 'Moyens de transport économiques ?']
      }
    },
    welcomeIntro: (name) => `Bonjour ${name} ! Je suis votre assistant de voyage IA V-OTA. Où souhaitez-vous partir, combien de jours et avec qui ?`,
    sharedTripWelcome: (sender, title, days, count) => `Bonjour ! Vous consultez l'itinéraire "${title}" partagé par ${sender}, comprenant ${days} jours et ${count} services réservables.`
  },

  ja: {
    assistantTitle: 'V-OTA AIトラベルアシスタント',
    assistantSubtitle: '100%実在する予約可能サービスと明確な料金でスマートな旅程を作成します。',
    headerBadge: 'AI旅行ガイド',
    inputPlaceholder: '質問例: 「家族でニャチャン3日間」「フーコックのおすすめグルメ」「ダナン5つ星ホテル」...',
    sendButton: '送信',
    voiceListening: '音声聞き取り中...',
    voiceListeningTooltip: 'ご希望の旅程をお話しください',
    clearChat: 'チャット初期化',
    itineraryTab: '旅程詳細',
    mapViewTab: 'ルートマップ',
    listViewTab: 'リスト表示',
    dayTabPrefix: '1日目',
    totalEstimated: '概算合計金額',
    bookableServices: '予約可能サービス',
    addToCartAll: 'すべてカートに追加',
    saveTrip: '旅程を保存',
    savedTrip: '保存済み',
    shareTrip: '共有',
    timeSlots: {
      morning: '午前',
      noon: '昼食',
      afternoon: '午後',
      evening: '夜'
    },
    roles: {
      general: {
        label: '総合案内',
        desc: '全体的なアドバイス、観光スポット、旅のコツ',
        welcomeMsg: 'こんにちは！V-OTA総合旅行アシスタントです。ベトナムの観光地、リゾートホテル、ツアーの手配をお手伝いします。',
        suggestedFollowUps: ['子連れ家族向けニャチャン3日間', 'カップル向けフーコック週末旅行', 'ダナン・ホイアン4日間の旅']
      },
      itinerary: {
        label: '旅程プランナー',
        desc: '朝・昼・夕・夜の時間帯別スケジュール最適化',
        welcomeMsg: 'こんにちは！旅程デザイン専門家です。移動時間と観光のバランスを考えた最適なスケジュールをご提案します。',
        suggestedFollowUps: ['日差しを避けた午前のプラン', '夜のおすすめ観光スポット', '午前中の離島巡り＆シュノーケリング']
      },
      culinary: {
        label: 'グルメ案内',
        desc: '名物料理、ナイトマーケット、評判の名店',
        welcomeMsg: 'こんにちは！ベトナムのグルメ＆カルチャー担当です。本場の名物料理やおすすめレストランをご案内します。',
        suggestedFollowUps: ['一番美味しい海鮮レストランは？', 'ナイトマーケットの必食グルメは？', '定番の朝食メニューは？']
      },
      budget: {
        label: '予算最適化',
        desc: 'お得なコンボパッケージと明確な費用見積もり',
        welcomeMsg: 'こんにちは！お得な割引パッケージや予算見積もりで、コスパ最高のベトナム旅行をお手伝いします！',
        suggestedFollowUps: ['20%お得なコンボプランは？', '3日間の予想費用内訳は？', '最も安くて便利な移動手段は？']
      }
    },
    welcomeIntro: (name) => `${name}様、こんにちは！V-OTA AIトラベルアシスタントです。行き先、日数、ご旅行の人数を教えてください。`,
    sharedTripWelcome: (sender, title, days, count) => `こんにちは！${sender}様から共有された「${title}」（${days}日間・${count}件の予約可能サービス）を表示しています。`
  },

  ko: {
    assistantTitle: 'V-OTA AI 여행 일정 어시스턴트',
    assistantSubtitle: '100% 예약 가능한 실제 여행 상품과 투명한 정가로 맞춤형 일정을 스마트하게 제안합니다.',
    headerBadge: '여행 AI',
    inputPlaceholder: '무엇이든 물어보세요: "가족과 함께 나트랑 3일", "푸꾸옥 맛집 추천", "다낭 리조트"...',
    sendButton: '전송',
    voiceListening: '음성 듣는 중...',
    voiceListeningTooltip: '여행 계획을 음성으로 말씀해주세요',
    clearChat: '대화 초기화',
    itineraryTab: '일정 상세',
    mapViewTab: '경로 지도',
    listViewTab: '상세 목록',
    dayTabPrefix: '일차',
    totalEstimated: '예상 총 비용',
    bookableServices: '예약 가능 상품',
    addToCartAll: '모두 장바구니에 담기',
    saveTrip: '일정 저장',
    savedTrip: '저장됨',
    shareTrip: '공유하기',
    timeSlots: {
      morning: '오전',
      noon: '점심',
      afternoon: '오후',
      evening: '저녁'
    },
    roles: {
      general: {
        label: '종합 안내',
        desc: '전반적인 여행 팁, 호텔 추천 및 관광지 정보',
        welcomeMsg: '안녕하세요! V-OTA AI 종합 여행 어시스턴트입니다. 베트남 여행에 필요한 모든 정보와 상품을 맞춤형으로 안내해 드립니다.',
        suggestedFollowUps: ['아이 동반 가족 나트랑 3일 코스', '커플 푸꾸옥 주말 힐링 여행', '다낭 & 호이안 4일 추천 코스']
      },
      itinerary: {
        label: '일정 플래너',
        desc: '오전·점심·오후·저녁 최적 동선 및 스케줄링',
        welcomeMsg: '안녕하세요! 일정 전문 어시스턴트입니다. 체력 소모를 줄이고 만족도를 극대화하는 시간대별 여행 일정을 설계해 드립니다.',
        suggestedFollowUps: ['더위를 피한 오전 맞춤 코스', '밤에 가기 좋은 야경 및 쇼', '오전 섬 투어 및 스노클링']
      },
      culinary: {
        label: '맛집 & 미식',
        desc: '현지 로컬 별미, 유명 야시장 및 해산물 맛집',
        welcomeMsg: '안녕하세요! 베트남 로컬 미식 가이드입니다. 진짜 현지인들이 찾는 숨은 맛집과 대표 요리를 찾아드립니다.',
        suggestedFollowUps: ['근처 최고의 싱싱한 해산물 맛집은?', '야시장에서 꼭 먹어봐야 할 것은?', '현지인 추천 아침 식사 맛집?']
      },
      budget: {
        label: '예산 절약',
        desc: '가성비 콤보 패키지 및 합리적인 경비 계획',
        welcomeMsg: '안녕하세요! 예산 최적화 전문가입니다. 호텔+티켓 콤보 혜택으로 여행 경비를 최대 20%까지 아껴드립니다.',
        suggestedFollowUps: ['20% 할인 콤보 패키지 추천?', '3일간 예상 총 경비는?', '가장 저렴하고 편리한 교통수단은?']
      }
    },
    welcomeIntro: (name) => `${name}님 안녕하세요! V-OTA AI 여행 어시스턴트입니다. 여행지, 일정, 동행 인원을 말씀해주시면 최적의 일정을 만들어 드릴게요!`,
    sharedTripWelcome: (sender, title, days, count) => `안녕하세요! ${sender}님이 공유한 "${title}" 일정(${days}일 일정, ${count}개 예약 가능 상품)입니다.`
  },

  zh: {
    assistantTitle: 'V-OTA AI 旅游行程助手',
    assistantSubtitle: '基于100%真实可预订产品与透明标价，一键生成智能个性化行程。',
    headerBadge: 'AI 旅游',
    inputPlaceholder: '随时提问：“亲子游芽庄3天”、“富国岛海鲜餐厅”、“岘港度假酒店”...',
    sendButton: '发送',
    voiceListening: '正在聆听语音...',
    voiceListeningTooltip: '语音输入您的旅行需求',
    clearChat: '重新开始对话',
    itineraryTab: '行程详情',
    mapViewTab: '路线地图',
    listViewTab: '详细列表',
    dayTabPrefix: '第',
    totalEstimated: '预计总费用',
    bookableServices: '项可预订服务',
    addToCartAll: '全部加入购物车',
    saveTrip: '收藏行程',
    savedTrip: '已收藏',
    shareTrip: '分享',
    timeSlots: {
      morning: '上午',
      noon: '中午',
      afternoon: '下午',
      evening: '晚上'
    },
    roles: {
      general: {
        label: '全能助手',
        desc: '目的地概览、酒店推荐与实用旅行贴士',
        welcomeMsg: '您好！我是 V-OTA 全能旅游助手。我可以为您规划越南旅行、推荐优质度假酒店及特色门票体验。',
        suggestedFollowUps: ['芽庄亲子游3天精华路线', '富国岛情侣浪漫周末度假', '岘港与会安古镇4日深度游']
      },
      itinerary: {
        label: '行程定制',
        desc: '上午、中午、下午与晚上的合理节奏安排',
        welcomeMsg: '您好！我是行程规划专家。我将为您优化每日时间分布与便捷路线，让旅途省心舒适。',
        suggestedFollowUps: ['避开正午烈日的早间行程', '晚上最值得打卡的夜市与演出', '上午跳岛浮潜与游船体验']
      },
      culinary: {
        label: '地道美食',
        desc: '本地特色风味、生猛海鲜及夜市必吃',
        welcomeMsg: '您好！我是越南美食与文化向导。您想探索哪些地道佳肴或高口碑海鲜餐厅？',
        suggestedFollowUps: ['附近最棒的新鲜海鲜大排档？', '夜市必尝的特色小吃推荐？', '当地人最爱的招牌早餐是什么？']
      },
      budget: {
        label: '预算省钱',
        desc: '精选超值套票、优惠满减与费用预估',
        welcomeMsg: '您好！我是预算与省钱专家。为您推荐立省20%的酒店加乐园门票组合与清晰花费清单！',
        suggestedFollowUps: ['有哪些立省20%的特惠组合？', '3天行程的花费预算大概多少？', '当地最划算便捷的出行方式？']
      }
    },
    welcomeIntro: (name) => `您好 ${name}！我是 V-OTA AI 旅游助手。请告诉我您计划去哪里、玩几天、几人同行？`,
    sharedTripWelcome: (sender, title, days, count) => `您好！您正在查看由 ${sender} 分享的行程“${title}”，共包含 ${days} 天规划与 ${count} 项可立即预订的真实服务。`
  },

  de: {
    assistantTitle: 'V-OTA KI-Reiseassistent',
    assistantSubtitle: 'Intelligente Reiseplanung mit 100% echten buchbaren Services und transparenten Preisen.',
    headerBadge: 'Reise-KI',
    inputPlaceholder: 'Fragen Sie alles: "3 Tage Nha Trang mit Familie", "Phu Quoc Meeresfrüchte"...',
    sendButton: 'Senden',
    voiceListening: 'Zuhören...',
    voiceListeningTooltip: 'Sprechen Sie Ihre Reisewünsche',
    clearChat: 'Chat zurücksetzen',
    itineraryTab: 'Reiseplan-Details',
    mapViewTab: 'Routenkarte',
    listViewTab: 'Listenansicht',
    dayTabPrefix: 'Tag',
    totalEstimated: 'Geschätzte Gesamtkosten',
    bookableServices: 'buchbare Services',
    addToCartAll: 'Alles in den Warenkorb',
    saveTrip: 'Reise speichern',
    savedTrip: 'Gespeichert',
    shareTrip: 'Teilen',
    timeSlots: {
      morning: 'Vormittag',
      noon: 'Mittag',
      afternoon: 'Nachmittag',
      evening: 'Abend'
    },
    roles: {
      general: {
        label: 'Allgemein',
        desc: 'Umfassende Beratung, Highlights und Reisetipps',
        welcomeMsg: 'Hallo! Ich bin Ihr V-OTA KI-Reiseassistent für Vietnam. Ich helfe Ihnen bei Touren, Hotels und Erlebnissen.',
        suggestedFollowUps: ['3 Tage Nha Trang für Familien', 'Wochenende auf Phu Quoc zu zweit', '4 Tage Da Nang und Hoi An']
      },
      itinerary: {
        label: 'Ablaufplan',
        desc: 'Optimale Zeiteinteilung nach Tageszeiten',
        welcomeMsg: 'Hallo! Ich bin Ihr Routenplaner. Ich optimiere Ihre Tageszeiten und Fahrstrecken für eine entspannte Reise.',
        suggestedFollowUps: ['Sonnengeschützter Vormittag für Kinder', 'Beste Abendunterhaltung und Shows', 'Vormittags Inseltour mit Schnorcheln']
      },
      culinary: {
        label: 'Kulinarik',
        desc: 'Authentische Spezialitäten und beste Restaurants',
        welcomeMsg: 'Hallo! Ich führe Sie durch Vietnams kulinarische Highlights und die besten Märkte.',
        suggestedFollowUps: ['Beste frische Meeresfrüchte am Strand?', 'Spezialitäten auf dem Nachtmarkt?', 'Beliebte Frühstückslokale?']
      },
      budget: {
        label: 'Budget',
        desc: 'Spar-Kombis und transparente Kostenaufstellung',
        welcomeMsg: 'Hallo! Ich helfe Ihnen, mit Kombi-Angeboten bis zu 20% bei Ihrem Vietnam-Urlaub zu sparen!',
        suggestedFollowUps: ['Kombi-Angebote mit Rabatt?', 'Kostenschätzung für 3 Tage?', 'Günstigste Transportmittel vor Ort?']
      }
    },
    welcomeIntro: (name) => `Hallo ${name}! Ich bin Ihr V-OTA KI-Reiseassistent. Wohin möchten Sie reisen und für wie viele Tage?`,
    sharedTripWelcome: (sender, title, days, count) => `Hallo! Sie sehen den Reiseplan "${title}" von ${sender} mit ${days} Tagen und ${count} buchbaren Leistungen.`
  },

  es: {
    assistantTitle: 'Asistente de Viajes IA V-OTA',
    assistantSubtitle: 'Planificación inteligente con 100% de servicios reales reservables y precios transparentes.',
    headerBadge: 'IA de Viajes',
    inputPlaceholder: 'Pregunta lo que quieras: "3 días en Nha Trang en familia", "mariscos en Phu Quoc"...',
    sendButton: 'Enviar',
    voiceListening: 'Escuchando...',
    voiceListeningTooltip: 'Habla sobre tus planes de viaje',
    clearChat: 'Reiniciar chat',
    itineraryTab: 'Detalles del viaje',
    mapViewTab: 'Mapa de ruta',
    listViewTab: 'Vista de lista',
    dayTabPrefix: 'Día',
    totalEstimated: 'Total estimado',
    bookableServices: 'servicios reservables',
    addToCartAll: 'Añadir todo al carrito',
    saveTrip: 'Guardar viaje',
    savedTrip: 'Guardado',
    shareTrip: 'Compartir',
    timeSlots: {
      morning: 'Mañana',
      noon: 'Mediodía',
      afternoon: 'Tarde',
      evening: 'Noche'
    },
    roles: {
      general: {
        label: 'General',
        desc: 'Asesoría completa, destinos destacados y consejos',
        welcomeMsg: '¡Hola! Soy tu asistente de viajes V-OTA en Vietnam. Te ayudo a planificar tu estancia, hoteles y tours.',
        suggestedFollowUps: ['3 días en Nha Trang para familias', 'Fin de semana en Phu Quoc en pareja', '4 días entre Da Nang y Hoi An']
      },
      itinerary: {
        label: 'Itinerario',
        desc: 'Distribución por horarios y rutas eficientes',
        welcomeMsg: '¡Hola! Soy tu especialista en itinerarios. Organizo tus días de forma cómoda y sin estrés.',
        suggestedFollowUps: ['Plan de mañana protegido del sol', 'Mejores lugares para salir de noche', 'Tour matutino por las islas y snorkel']
      },
      culinary: {
        label: 'Gastronomía',
        desc: 'Platos típicos locales y restaurantes recomendados',
        welcomeMsg: '¡Hola! Te guiaré por la exquisita gastronomía vietnamita y sus mercados locales.',
        suggestedFollowUps: ['¿Los mejores mariscos frescos frente al mar?', '¿Qué probar en el mercado nocturno?', '¿Desayunos típicos recomendados?']
      },
      budget: {
        label: 'Presupuesto',
        desc: 'Ofertas combinadas y cálculo claro de costes',
        welcomeMsg: '¡Hola! Te ayudo a ahorrar hasta un 20% con paquetes combinados y presupuestos detallados.',
        suggestedFollowUps: ['¿Paquetes con descuento del 20%?', '¿Presupuesto estimado para 3 días?', '¿Transporte más económico?']
      }
    },
    welcomeIntro: (name) => `¡Hola ${name}! Soy tu asistente IA de V-OTA. ¿A dónde te gustaría viajar, cuántos días y con quién?`,
    sharedTripWelcome: (sender, title, days, count) => `¡Hola! Estás viendo el itinerario "${title}" compartido por ${sender}, con ${days} días y ${count} servicios reservables.`
  },

  ru: {
    assistantTitle: 'ИИ-помощник по путешествиям V-OTA',
    assistantSubtitle: 'Умное планирование маршрута со 100% реальными бронируемыми услугами и прозрачными ценами.',
    headerBadge: 'ИИ Путешествия',
    inputPlaceholder: 'Спросите о чем угодно: «3 дня в Нячанге с семьей», «морепродукты Фукуока»...',
    sendButton: 'Отправить',
    voiceListening: 'Слушаю...',
    voiceListeningTooltip: 'Произнесите ваши пожелания',
    clearChat: 'Очистить чат',
    itineraryTab: 'Детали маршрута',
    mapViewTab: 'Карта маршрута',
    listViewTab: 'Список',
    dayTabPrefix: 'День',
    totalEstimated: 'Ориентировочная сумма',
    bookableServices: 'доступных услуг',
    addToCartAll: 'Добавить все в корзину',
    saveTrip: 'Сохранить',
    savedTrip: 'Сохранено',
    shareTrip: 'Поделиться',
    timeSlots: {
      morning: 'Утро',
      noon: 'Обед',
      afternoon: 'День',
      evening: 'Вечер'
    },
    roles: {
      general: {
        label: 'Общий',
        desc: 'Советы по путешествиям, подбор курортов и отелей',
        welcomeMsg: 'Здравствуйте! Я ваш ИИ-помощник V-OTA во Вьетнаме. Помогу спланировать поездку, забронировать отели и экскурсии.',
        suggestedFollowUps: ['3 дня в Нячанге для семьи с детьми', 'Выходные на Фукуоке для двоих', '4 дня в Дананге и Хойане']
      },
      itinerary: {
        label: 'Маршрут',
        desc: 'Почасовое расписание (утро - обед - день - вечер)',
        welcomeMsg: 'Здравствуйте! Я специалист по составлению маршрутов. Оптимизирую время и логистику для приятного отдыха.',
        suggestedFollowUps: ['Утренний маршрут в тени для детей', 'Куда пойти вечером на шоу?', 'Утренняя морская прогулка со снорклингом']
      },
      culinary: {
        label: 'Кулинария',
        desc: 'Настоящая вьетнамская кухня и свежие морепродукты',
        welcomeMsg: 'Здравствуйте! Я ваш гастрономический гид. Расскажу о лучших ресторанах и колоритных рынках.',
        suggestedFollowUps: ['Где самые свежие морепродукты?', 'Что попробовать на ночном рынке?', 'Популярные блюда на завтрак?']
      },
      budget: {
        label: 'Бюджет',
        desc: 'Выгодные комбо-пакеты и расчет расходов',
        welcomeMsg: 'Здравствуйте! Помогу сэкономить до 20% благодаря комбо-билетам и прозрачному расчету бюджета.',
        suggestedFollowUps: ['Выгодные комбо со скидкой 20%?', 'Ориентировочный бюджет на 3 дня?', 'Самый недорогой местный транспорт?']
      }
    },
    welcomeIntro: (name) => `Здравствуйте, ${name}! Я ваш ИИ-помощник V-OTA. Куда планируете поехать, на сколько дней и в каком составе?`,
    sharedTripWelcome: (sender, title, days, count) => `Здравствуйте! Вы просматриваете маршрут «${title}», которым поделился(лась) ${sender} (${days} дн., ${count} услуг).`
  },

  th: {
    assistantTitle: 'ผู้ช่วยวางแผนเที่ยว AI V-OTA',
    assistantSubtitle: 'วางแผนการเดินทางอัจฉริยะด้วยบริการจริง 100% ราคาชัดเจน จองสะดวกในคลิกเดียว',
    headerBadge: 'AI ท่องเที่ยว',
    inputPlaceholder: 'ถามได้ทุกเรื่อง: "ญาจาง 3 วันสำหรับครอบครัว", "ซีฟู้ดฟูก๊วก", "โรงแรมฮอยอัน"...',
    sendButton: 'ส่ง',
    voiceListening: 'กำลังฟังเสียง...',
    voiceListeningTooltip: 'พูดความต้องการในการเดินทางของคุณ',
    clearChat: 'เริ่มคุยใหม่',
    itineraryTab: 'รายละเอียดแผนเที่ยว',
    mapViewTab: 'แผนที่เส้นทาง',
    listViewTab: 'มุมมองรายการ',
    dayTabPrefix: 'วันที่',
    totalEstimated: 'ค่าใช้จ่ายโดยประมาณ',
    bookableServices: 'บริการที่จองได้',
    addToCartAll: 'เพิ่มทั้งหมดลงตะกร้า',
    saveTrip: 'บันทึกทริป',
    savedTrip: 'บันทึกแล้ว',
    shareTrip: 'แชร์',
    timeSlots: {
      morning: 'ช่วงเช้า',
      noon: 'ช่วงเที่ยง',
      afternoon: 'ช่วงบ่าย',
      evening: 'ช่วงค่ำ'
    },
    roles: {
      general: {
        label: 'ทั่วไป',
        desc: 'คำแนะนำภาพรวม แหล่งท่องเที่ยว และเคล็ดลับการเดินทาง',
        welcomeMsg: 'สวัสดีครับ! ผมคือผู้ช่วยท่องเที่ยว V-OTA ยินดีช่วยวางแผน จองที่พัก และกิจกรรมท่องเที่ยวในเวียดนามครับ',
        suggestedFollowUps: ['เที่ยวญาจาง 3 วันสำหรับครอบครัว', 'ฟูก๊วกสุดสัปดาห์สำหรับคู่รัก', 'เที่ยวดานังและฮอยอัน 4 วัน']
      },
      itinerary: {
        label: 'แผนการเดินทาง',
        desc: 'จัดสรรเวลา เช้า-เที่ยง-บ่าย-ค่ำ อย่างลงตัว',
        welcomeMsg: 'สวัสดีครับ! ผมคือผู้เชี่ยวชาญการจัดแผนเที่ยว จะช่วยจัดสรรเวลาและการเดินทางให้คุ้มค่าและไม่เหนื่อยครับ',
        suggestedFollowUps: ['แผนช่วงเช้าหลบแดดสำหรับเด็ก', 'สถานที่เที่ยวยามค่ำคืนและการแสดงสุดอลังการ', 'ทัวร์ดำน้ำเกาะช่วงเช้า']
      },
      culinary: {
        label: 'อาหาร & วัฒนธรรม',
        desc: 'อาหารพื้นเมืองเลื่องชื่อและร้านอาหารเด็ด',
        welcomeMsg: 'สวัสดีครับ! ผมพร้อมแนะนำอาหารเวียดนามจานเด็ด อาหารทะเลสดๆ และตลาดกลางคืนที่ไม่ควรพลาดครับ',
        suggestedFollowUps: ['ร้านอาหารทะเลสดริมหาดที่ดีที่สุด?', 'ของกินเด็ดตลาดกลางคืน?', 'เมนูอาหารเช้าขึ้นชื่อของท้องถิ่น?']
      },
      budget: {
        label: 'ประหยัดงบ',
        desc: 'แพ็กเกจคอมโบสุดคุ้มและประมาณการค่าใช้จ่าย',
        welcomeMsg: 'สวัสดีครับ! ผมจะช่วยคุณประหยัดงบด้วยแพ็กเกจคอมโบลดสูงสุด 20% พร้อมสรุปค่าใช้จ่ายชัดเจนครับ',
        suggestedFollowUps: ['แพ็กเกจคอมโบลด 20% มีอะไรบ้าง?', 'งบประมาณประมาณการ 3 วัน?', 'วิธีเดินทางที่คุ้มค่าที่สุด?']
      }
    },
    welcomeIntro: (name) => `สวัสดีคุณ ${name}! ผมคือผู้ช่วย AI ท่องเที่ยว V-OTA มีแผนอยากไปเที่ยวที่ไหน กี่วัน และไปกับใคร บอกผมได้เลยครับ!`,
    sharedTripWelcome: (sender, title, days, count) => `สวัสดีครับ! คุณกำลังดูแผนการเดินทาง "${title}" ที่แชร์โดย ${sender} ทั้งหมด ${days} วัน พร้อม ${count} บริการที่จองได้ทันที`
  }
};

// Initialize helper methods and component aliases across all supported locales
(Object.keys(TRANSLATIONS) as SupportedLocale[]).forEach((loc) => {
  const t = TRANSLATIONS[loc];
  t.day = (d: number) => {
    if (loc === 'ja') return `${d}日目`;
    if (loc === 'ko') return `${d}일차`;
    if (loc === 'zh') return `第 ${d} 天`;
    return `${t.dayTabPrefix || 'Ngày'} ${d}`;
  };
  t.aiAssistantTitle = t.aiAssistantTitle || t.assistantTitle;
  t.aiAssistantSubtitle = t.aiAssistantSubtitle || t.assistantSubtitle;
  t.send = t.send || t.sendButton;
  t.saved = t.saved || t.savedTrip;
  t.savedTrips = t.savedTrips || (loc === 'vi' ? 'Chuyến đã lưu' : 'Saved Trips');
  t.share = t.share || t.shareTrip;
  t.listView = t.listView || t.listViewTab;
  t.mapView = t.mapView || t.mapViewTab;
  t.stayEntireTrip = t.stayEntireTrip || (loc === 'vi' ? 'Khách sạn lưu trú suốt chuyến đi' : 'Accommodation for entire trip');
  t.viewRoute = t.viewRoute || (loc === 'vi' ? 'Xem lộ trình' : 'View route');
  t.morning = t.morning || t.timeSlots?.morning || (loc === 'vi' ? 'Buổi sáng' : 'Morning');
  t.noon = t.noon || t.timeSlots?.noon || (loc === 'vi' ? 'Buổi trưa' : 'Noon');
  t.afternoon = t.afternoon || t.timeSlots?.afternoon || (loc === 'vi' ? 'Buổi chiều' : 'Afternoon');
  t.evening = t.evening || t.timeSlots?.evening || (loc === 'vi' ? 'Buổi tối' : 'Evening');
  t.estimated = t.estimated || (loc === 'vi' ? 'ước tính' : 'estimated');
  t.addAllToCart = t.addAllToCart || t.addToCartAll;
  t.locatedCoordinates = t.locatedCoordinates || (loc === 'vi' ? 'Tọa độ vị trí & Lộ trình di chuyển thông minh' : 'Geolocated coordinates & smart itinerary routing');
  t.processing = t.processing || (loc === 'vi' ? 'Đang phân tích & tối ưu lịch trình...' : 'Analyzing & optimizing itinerary...');
  t.step1 = t.step1 || (loc === 'vi' ? 'Phân tích điểm đến & nhu cầu du khách' : 'Analyzing destination & preferences');
  t.step2 = t.step2 || (loc === 'vi' ? 'Truy xuất sản phẩm thật từ kho V-OTA' : 'Retrieving real products from V-OTA inventory');
  t.step3 = t.step3 || (loc === 'vi' ? 'Sắp xếp lộ trình theo buổi hợp lý' : 'Arranging optimal daily time slots');
  t.noPlanSelected = t.noPlanSelected || (loc === 'vi' ? 'Chưa có lịch trình nào được chọn' : 'No itinerary selected');
  t.noPlanHint = t.noPlanHint || (loc === 'vi' ? 'Hãy hỏi Trợ lý AI hoặc chọn một gợi ý để bắt đầu lên lịch trình thật.' : 'Ask the AI Assistant or pick a suggested prompt to generate a grounded itinerary.');
});

/**
 * Format a price value nicely based on target locale
 */
export function formatLocalizedCurrency(amountVND: number, locale: SupportedLocale): { formatted: string; secondary?: string } {
  const localeInfo = SUPPORTED_LOCALES.find(l => l.code === locale) || SUPPORTED_LOCALES[0];
  
  if (locale === 'vi') {
    return {
      formatted: `${new Intl.NumberFormat('vi-VN').format(amountVND)} ₫`
    };
  }

  // Foreign currency conversion
  const converted = Math.round(amountVND / localeInfo.currencyRateToVND);
  let formattedForeign = '';

  switch (locale) {
    case 'en':
      formattedForeign = `$${new Intl.NumberFormat('en-US').format(converted)}`;
      break;
    case 'fr':
    case 'de':
    case 'es':
      formattedForeign = `${new Intl.NumberFormat('de-DE').format(converted)} €`;
      break;
    case 'ja':
      formattedForeign = `¥${new Intl.NumberFormat('ja-JP').format(converted)}`;
      break;
    case 'ko':
      formattedForeign = `₩${new Intl.NumberFormat('ko-KR').format(converted)}`;
      break;
    case 'zh':
      formattedForeign = `¥${new Intl.NumberFormat('zh-CN').format(converted)}`;
      break;
    case 'ru':
      formattedForeign = `${new Intl.NumberFormat('ru-RU').format(converted)} ₽`;
      break;
    case 'th':
      formattedForeign = `${new Intl.NumberFormat('th-TH').format(converted)} ฿`;
      break;
    default:
      formattedForeign = `$${converted}`;
  }

  return {
    formatted: formattedForeign,
    secondary: `~${new Intl.NumberFormat('vi-VN').format(amountVND)} ₫`
  };
}

/**
 * Real-time itinerary plan translator
 * Ensures day titles, notes, and activity headers adapt when switching locale
 */
export function localizePlan(plan: GroundedPlan, targetLocale: SupportedLocale): GroundedPlan {
  if (!plan) return plan;

  const t = TRANSLATIONS[targetLocale] || TRANSLATIONS.vi;
  const dest = plan.intent.destination;

  // Localized destination names
  const destNames: Record<string, Record<SupportedLocale, string>> = {
    'Nha Trang': {
      vi: 'Nha Trang', en: 'Nha Trang', fr: 'Nha Trang', ja: 'ニャチャン', ko: '나트랑', zh: '芽庄', de: 'Nha Trang', es: 'Nha Trang', ru: 'Нячанг', th: 'ญาจาง'
    },
    'Phú Quốc': {
      vi: 'Phú Quốc', en: 'Phu Quoc Island', fr: 'Île de Phu Quoc', ja: 'フーコック島', ko: '푸꾸옥', zh: '富国岛', de: 'Insel Phu Quoc', es: 'Isla de Phu Quoc', ru: 'Остров Фукуок', th: 'เกาะฟูก๊วก'
    },
    'Đà Nẵng': {
      vi: 'Đà Nẵng', en: 'Da Nang', fr: 'Da Nang', ja: 'ダナン', ko: '다낭', zh: '岘港', de: 'Da Nang', es: 'Da Nang', ru: 'Дананг', th: 'ดานัง'
    },
    'Hội An': {
      vi: 'Hội An', en: 'Hoi An Ancient Town', fr: 'Vieille ville de Hoi An', ja: 'ホイアン', ko: '호이안', zh: '会安古镇', de: 'Altstadt Hoi An', es: 'Ciudad Antigua de Hoi An', ru: 'Хойан', th: 'ฮอยอัน'
    },
    'Hạ Long': {
      vi: 'Hạ Long', en: 'Ha Long Bay', fr: 'Baie d\'Ha Long', ja: 'ハロン湾', ko: '하롱베이', zh: '下龙湾', de: 'Ha Long Bucht', es: 'Bahía de Ha Long', ru: 'Бухта Халонг', th: 'อ่าวฮาลอง'
    },
    'Hà Nội': {
      vi: 'Hà Nội', en: 'Hanoi', fr: 'Hanoï', ja: 'ハノイ', ko: '하노이', zh: '河内', de: 'Hanoi', es: 'Hanói', ru: 'Ханой', th: 'ฮานอย'
    }
  };

  const localizedDest = destNames[dest]?.[targetLocale] || dest;

  // Day titles localized templates
  const dayTitlesMap: Record<number, Record<SupportedLocale, string>> = {
    1: {
      vi: 'Chào đón vịnh biển & Vui chơi giải trí',
      en: 'Coastal Welcome & Theme Park Adventures',
      fr: 'Bienvenue sur la côte & Divertissements',
      ja: '海辺の歓迎とテーマパークアドベンチャー',
      ko: '해변 도착 환영 & 테마파크 어드벤처',
      zh: '海滨欢迎之旅与主题乐园狂欢',
      de: 'Willkommen an der Küste & Erlebnispark',
      es: 'Bienvenida costera y parque de atracciones',
      ru: 'Встреча на побережье и парк развлечений',
      th: 'ต้อนรับสู่ชายหาด & ผจญภัยสวนสนุก'
    },
    2: {
      vi: 'Khám phá văn hóa & Trải nghiệm biển đảo',
      en: 'Island Hopping & Cultural Discovery',
      fr: 'Exploration culturelle & Croisière insulaire',
      ja: '文化探訪と離島クルーズ体験',
      ko: '문화 탐방 & 섬 투어 힐링 체험',
      zh: '海岛探索与地道文化体验',
      de: 'Inselhopping & Kulturelle Entdeckungen',
      es: 'Recorrido por las islas y descubrimiento cultural',
      ru: 'Морская прогулка по островам и культура',
      th: 'ล่องเรือชมเกาะ & สัมผัสวัฒนธรรมท้องถิ่น'
    },
    3: {
      vi: 'Thư giãn nghỉ dưỡng & Thưởng thức ẩm thực',
      en: 'Resort Relaxation & Gastronomic Delights',
      fr: 'Détente au resort & Dégustation gastronomique',
      ja: 'リゾートでのリラックスと極上グルメ',
      ko: '리조트 휴식 & 로컬 미식 투어',
      zh: '高端度假疗愈与地道美食品鉴',
      de: 'Entspannung im Resort & Kulinarische Genüsse',
      es: 'Relajación en el resort y delicias gastronómicas',
      ru: 'Отдых на курорте и гастрономические открытия',
      th: 'พักผ่อนในรีสอร์ต & ลิ้มลองอาหารรสเลิศ'
    }
  };

  // Localized general plan title
  const localizedTitle = targetLocale === 'vi' 
    ? plan.title 
    : targetLocale === 'en'
    ? `${plan.intent.days}-Day Premium Travel Plan for ${localizedDest}`
    : targetLocale === 'fr'
    ? `Séjour de ${plan.intent.days} jours d'exception à ${localizedDest}`
    : targetLocale === 'ja'
    ? `${localizedDest}を満喫する${plan.intent.days}日間のプレミアム旅行プラン`
    : targetLocale === 'ko'
    ? `${localizedDest} ${plan.intent.days}일 맞춤형 프리미엄 여행 일정`
    : targetLocale === 'zh'
    ? `${localizedDest} ${plan.intent.days} 天轻奢精选旅行方案`
    : targetLocale === 'de'
    ? `${plan.intent.days}-tägige Premium-Reise nach ${localizedDest}`
    : targetLocale === 'es'
    ? `Viaje de ${plan.intent.days} días en ${localizedDest}`
    : targetLocale === 'ru'
    ? `Маршрут на ${plan.intent.days} дн. в ${localizedDest}`
    : `ทริปท่องเที่ยว ${localizedDest} ${plan.intent.days} วันสุดพิเศษ`;

  const localizedDays = plan.days.map((d, index) => {
    const dayNum = d.day || (index + 1);
    const dayTitle = dayTitlesMap[dayNum]?.[targetLocale] || 
      `${t.dayTabPrefix} ${dayNum}: ${localizedDest}`;

    const localizedSlots = d.slots.map(s => {
      const slotCopy: ItinerarySlot = { ...s };

      // Localize non-bookable activity notes
      if (s.isActivityNote) {
        if (s.time === 'noon') {
          slotCopy.activityTitle = {
            vi: 'Nghỉ ngơi & Ăn trưa ẩm thực địa phương',
            en: 'Lunch Break & Local Specialties',
            fr: 'Déjeuner & Spécialités locales',
            ja: 'ランチ休憩＆地元名物料理',
            ko: '점심 식사 & 로컬 미식 체험',
            zh: '午间小憩与品尝地道风味',
            de: 'Mittagspause & Lokale Spezialitäten',
            es: 'Almuerzo y especialidades locales',
            ru: 'Обед и дегустация местных блюд',
            th: 'พักรับประทานอาหารกลางวันพื้นเมือง'
          }[targetLocale];

          slotCopy.note = {
            vi: 'Thưởng thức bữa trưa đặc sản địa phương tươi sống tại khu ẩm thực, nghỉ ngơi lấy lại năng lượng.',
            en: 'Enjoy fresh local specialties at recommended culinary spots and take a relaxing midday break.',
            fr: 'Savourez les spécialités locales fraîches et profitez d\'une pause reposante à midi.',
            ja: '地元の人気レストランで新鮮な郷土料理を味わい、午後に向けてゆっくり休憩します。',
            ko: '엄선된 로컬 식당에서 신선한 별미 점심을 즐기며 여유롭게 체력을 충전합니다.',
            zh: '在口碑餐厅享用新鲜的海鲜与招牌特色午餐，惬意休憩避暑。',
            de: 'Genießen Sie frische Spezialitäten in ausgewählten Lokalen und erholen Sie sich mittags.',
            es: 'Disfruta de delicias locales frescas y descansa antes de las actividades de la tarde.',
            ru: 'Попробуйте свежие местные деликатесы и отдохните в полуденное время.',
            th: 'อิ่มอร่อยกับอาหารท้องถิ่นรสเลิศและพักผ่อนเติมพลังในช่วงกลางวัน'
          }[targetLocale];
        } else if (s.time === 'morning') {
          slotCopy.activityTitle = {
            vi: 'Tắm biển & Dạo ngắm bình minh trên bãi cát',
            en: 'Morning Beach Walk & Sunrise Swims',
            fr: 'Balade matinale sur la plage & Baignade',
            ja: '朝のビーチ散歩と日の出スイミング',
            ko: '모닝 해변 산책 & 일출 감상',
            zh: '晨光海滩漫步与清凉晨泳',
            de: 'Morgendlicher Strandspaziergang & Sonnenaufgang',
            es: 'Paseo matinal por la playa y amanecer',
            ru: 'Утренняя прогулка по пляжу и рассвет',
            th: 'เดินเล่นชายหาดยามเช้า & ชมพระอาทิตย์ขึ้น'
          }[targetLocale];

          slotCopy.note = {
            vi: 'Thức dậy ngắm bình minh tuyệt đẹp, tắm biển tại bãi tắm riêng của khu nghỉ dưỡng và dùng buffet sáng.',
            en: 'Wake up to a golden sunrise, enjoy a morning swim along pristine sands, and indulge in breakfast.',
            fr: 'Réveillez-vous devant un lever de soleil sublime, baignez-vous et profitez d\'un petit-déjeuner copieux.',
            ja: '美しい日の出を眺めながら澄んだ海で泳ぎ、優雅な朝食ビュッフェを満喫します。',
            ko: '눈부신 일출과 함께 프라이빗 비치에서 모닝 수영을 즐기고 조식 뷔페를 맛봅니다.',
            zh: '在金色日出中醒来，于度假村专属沙滩漫步晨泳，享用丰盛早餐。',
            de: 'Erleben Sie den Sonnenaufgang am Meer und genießen Sie ein reichhaltiges Frühstück.',
            es: 'Despiértate con un amanecer radiante, disfruta de un baño en la playa y toma un desayuno buffet.',
            ru: 'Встречайте живописный рассвет на песчаном берегу и наслаждайтесь утренним плаванием.',
            th: 'ตื่นเช้าชมพระอาทิตย์ขึ้นริมหาด ลงเล่นน้ำทะเลใส และอิ่มอร่อยกับบุฟเฟต์มื้อเช้า'
          }[targetLocale];
        }
      }

      return slotCopy;
    });

    return {
      ...d,
      title: dayTitle,
      slots: localizedSlots
    };
  });

  return {
    ...plan,
    title: localizedTitle,
    days: localizedDays
  };
}

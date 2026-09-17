export type SupportedLocale = 
  | 'vi' 
  | 'en' 
  | 'fr' 
  | 'ja' 
  | 'ko' 
  | 'zh' 
  | 'de' 
  | 'es' 
  | 'ru' 
  | 'th';

export interface LocaleInfo {
  code: SupportedLocale;
  name: string;
  nativeName: string;
  flag: string;
  speechLang: string;
  englishName: string;
  currencyCode: string;
  currencyRateToVND: number; // 1 unit in foreign currency = X VND
}

export const SUPPORTED_LOCALES: LocaleInfo[] = [
  {
    code: 'vi',
    name: 'Tiếng Việt',
    nativeName: 'Tiếng Việt',
    flag: '🇻🇳',
    speechLang: 'vi-VN',
    englishName: 'Vietnamese',
    currencyCode: 'VND',
    currencyRateToVND: 1
  },
  {
    code: 'en',
    name: 'English',
    nativeName: 'English (US)',
    flag: '🇺🇸',
    speechLang: 'en-US',
    englishName: 'English',
    currencyCode: 'USD',
    currencyRateToVND: 25400
  },
  {
    code: 'fr',
    name: 'Français',
    nativeName: 'Français',
    flag: '🇫🇷',
    speechLang: 'fr-FR',
    englishName: 'French',
    currencyCode: 'EUR',
    currencyRateToVND: 27500
  },
  {
    code: 'ja',
    name: 'Tiếng Nhật',
    nativeName: '日本語',
    flag: '🇯🇵',
    speechLang: 'ja-JP',
    englishName: 'Japanese',
    currencyCode: 'JPY',
    currencyRateToVND: 168
  },
  {
    code: 'ko',
    name: 'Tiếng Hàn',
    nativeName: '한국어',
    flag: '🇰🇷',
    speechLang: 'ko-KR',
    englishName: 'Korean',
    currencyCode: 'KRW',
    currencyRateToVND: 18.5
  },
  {
    code: 'zh',
    name: 'Tiếng Trung',
    nativeName: '中文 (简体)',
    flag: '🇨🇳',
    speechLang: 'zh-CN',
    englishName: 'Chinese',
    currencyCode: 'CNY',
    currencyRateToVND: 3520
  },
  {
    code: 'de',
    name: 'Tiếng Đức',
    nativeName: 'Deutsch',
    flag: '🇩🇪',
    speechLang: 'de-DE',
    englishName: 'German',
    currencyCode: 'EUR',
    currencyRateToVND: 27500
  },
  {
    code: 'es',
    name: 'Tiếng Tây Ban Nha',
    nativeName: 'Español',
    flag: '🇪🇸',
    speechLang: 'es-ES',
    englishName: 'Spanish',
    currencyCode: 'EUR',
    currencyRateToVND: 27500
  },
  {
    code: 'ru',
    name: 'Tiếng Nga',
    nativeName: 'Русский',
    flag: '🇷🇺',
    speechLang: 'ru-RU',
    englishName: 'Russian',
    currencyCode: 'RUB',
    currencyRateToVND: 275
  },
  {
    code: 'th',
    name: 'Tiếng Thái',
    nativeName: 'ไทย',
    flag: '🇹🇭',
    speechLang: 'th-TH',
    englishName: 'Thai',
    currencyCode: 'THB',
    currencyRateToVND: 720
  }
];

export const DEFAULT_LOCALE: SupportedLocale = 'vi';

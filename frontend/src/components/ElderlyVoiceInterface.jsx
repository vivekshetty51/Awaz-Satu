import React, { useState } from 'react';
import {
  Volume2,
  RotateCcw,
  Sparkles,
  Phone,
  Mic,
  ExternalLink,
  ShieldCheck,
  CheckCircle2,
  Heart,
  Landmark,
} from 'lucide-react';
import GoogleMicrophone from './GoogleMicrophone';

export default function ElderlyVoiceInterface({
  voiceAssistant,
  onOpenDialer,
}) {
  const {
    isListening,
    isProcessing,
    isSpeaking,
    volume,
    barLevels,
    language,
    setLanguage,
    userTranscript,
    aiResponse,
    dpiData,
    error,
    toggleListen,
    stopSpeaking,
    replayAudio,
    executeQuery,
  } = voiceAssistant;

  const [activeTab, setActiveTab] = useState('voice'); // 'voice' | 'schemes'

  // Multilingual content for elderly citizens
  const content = {
    en: {
      appName: 'Awaaz Setu',
      tagline: 'Karnataka Citizen Voice Assistance',
      elderTip: 'Designed for Senior Citizens: Just tap the mic and speak naturally.',
      langSelect: 'Language / ಭಾಷೆ:',
      youSaid: 'You Asked:',
      govAnswer: 'Government Answer:',
      replay: 'Listen Again (Replay)',
      popularSchemes: 'Popular Karnataka Schemes:',
      schemes: [
        {
          id: 'sandhya',
          title: 'Sandhya Suraksha (Old Age Pension)',
          desc: '₹1,000/mo pension for senior citizens aged 65+',
          query: 'How can senior citizens get 1000 rupees monthly pension under Sandhya Suraksha scheme?',
          icon: '👴',
          tag: 'DSSP Portal',
        },
        {
          id: 'gruha_lakshmi',
          title: 'Gruha Lakshmi (₹2,000/mo)',
          desc: '₹2,000 monthly benefit for women head of family',
          query: 'How to apply for Gruha Lakshmi scheme 2000 rupees monthly benefit on Seva Sindhu?',
          icon: '👵',
          tag: 'Seva Sindhu',
        },
        {
          id: 'bhoomi',
          title: 'Bhoomi Land Records (RTC / Pahani)',
          desc: 'View and download land ownership RTC records',
          query: 'How can I download my land RTC Pahani from Bhoomi portal in Karnataka?',
          icon: '🌾',
          tag: 'Bhoomi Portal',
        },
        {
          id: 'gruha_jyothi',
          title: 'Gruha Jyothi (200 Free Units)',
          desc: 'Free electricity up to 200 units every month',
          query: 'What is the eligibility for Gruha Jyothi 200 free units electricity in Karnataka?',
          icon: '💡',
          tag: 'BESCOM / Energy',
        },
        {
          id: 'anna_bhagya',
          title: 'Anna Bhagya (Free Rice & DBT)',
          desc: 'Free food grains and cash transfer for BPL/AAY',
          query: 'What are the benefits and DBT cash status of Anna Bhagya food scheme?',
          icon: '🍚',
          tag: 'Ahara Portal',
        },
        {
          id: 'arogya',
          title: 'Arogya Karnataka (Free Healthcare)',
          desc: 'Cashless hospital treatment up to ₹5 lakh',
          query: 'How to get free cashless treatment up to 5 lakh under Arogya Karnataka scheme?',
          icon: '🏥',
          tag: 'SAST Portal',
        },
      ],
    },
    kn: {
      appName: 'ಆವಾಜ್ ಸೇತು',
      tagline: 'ಕರ್ನಾಟಕ ಸರ್ಕಾರದ ಧ್ವನಿ ಸೇವೆ',
      elderTip: 'ಹಿರಿಯ ನಾಗರಿಕರಿಗೆ ಸುಲಭ ಧ್ವನಿ ಸೇವೆ: ದೊಡ್ಡ ಮೈಕ್ ಒತ್ತಿ ನೇರವಾಗಿ ಮಾತನಾಡಿ.',
      langSelect: 'ಭಾಷೆ / Language:',
      youSaid: 'ನೀವು ಕೇಳಿದ ಪ್ರಶ್ನೆ:',
      govAnswer: 'ಸರ್ಕಾರದ ಅಧಿಕೃತ ಮಾಹಿತಿ:',
      replay: 'ಮತ್ತೊಮ್ಮೆ ಧ್ವನಿ ಕೇಳಿ (Replay)',
      popularSchemes: 'ಪ್ರಮುಖ ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು:',
      schemes: [
        {
          id: 'sandhya',
          title: 'ಸಂಧ್ಯಾ ಸುರಕ್ಷಾ (ಹಿರಿಯರ ಮಾಸಾಶನ)',
          desc: '65 ವರ್ಷ ಮೇಲ್ಪಟ್ಟ ಹಿರಿಯರಿಗೆ ತಿಂಗಳಿಗೆ ₹1,000 ಮಾಸಾಶನ',
          query: 'ಸಂಧ್ಯಾ ಸುರಕ್ಷಾ ಯೋಜನೆಯಲ್ಲಿ ಹಿರಿಯ ನಾಗರಿಕರಿಗೆ ತಿಂಗಳಿಗೆ 1000 ರೂಪಾಯಿ ಪಿಂಚಣಿ ಹೇಗೆ ಸಿಗುತ್ತದೆ?',
          icon: '👴',
          tag: 'DSSP ಇಲಾಖೆ',
        },
        {
          id: 'gruha_lakshmi',
          title: 'ಗೃಹಲಕ್ಷ್ಮಿ ಯೋಜನೆ (ತಿಂಗಳಿಗೆ ₹2,000)',
          desc: 'ಮನೆಯ ಯಜಮಾನಿ ಮಹಿಳೆಗೆ ಪ್ರತಿ ತಿಂಗಳು ₹2,000',
          query: 'ಗೃಹಲಕ್ಷ್ಮಿ ಯೋಜನೆಯ ₹2,000 ಹಣ ಪಡೆಯಲು ಸೇವಾ ಸಿಂಧು ಪೋರ್ಟಲ್‌ನಲ್ಲಿ ಹೇಗೆ ಅರ್ಜಿ ಸಲ್ಲಿಸಬೇಕು?',
          icon: '👵',
          tag: 'ಸೇವಾ ಸಿಂಧು',
        },
        {
          id: 'bhoomi',
          title: 'ಭೂಮಿ ಪೋರ್ಟಲ್ (ಜಮೀನು ಪಹಣಿ / RTC)',
          desc: 'ನಿಮ್ಮ ಜಮೀನಿನ ಪಹಣಿ (RTC) ಡೌನ್‌ಲೋಡ್ ಮಾಡುವ ವಿಧಾನ',
          query: 'ಭೂಮಿ ಪೋರ್ಟಲ್‌ನಿಂದ ಜಮೀನಿನ ಆರ್‌ಟಿಸಿ ಪಹಣಿ ಹೇಗೆ ಡೌನ್‌ಲೋಡ್ ಮಾಡಿಕೊಳ್ಳಬಹುದು?',
          icon: '🌾',
          tag: 'ಭೂಮಿ ಪೋರ್ಟಲ್',
        },
        {
          id: 'gruha_jyothi',
          title: 'ಗೃಹಜ್ಯೋತಿ (200 ಯೂನಿಟ್ ಉಚಿತ ಕರೆಂಟ್)',
          desc: 'ಮನೆಬಳಕೆಗೆ ಪ್ರತಿ ತಿಂಗಳು 200 ಯೂನಿಟ್ ಉಚಿತ ವಿದ್ಯುತ್',
          query: 'ಗೃಹಜ್ಯೋತಿ ಯೋಜನೆಯಡಿ 200 ಯೂನಿಟ್ ಉಚಿತ ಕರೆಂಟ್ ಪಡೆಯಲು ಯಾರು ಅರ್ಹರು?',
          icon: '💡',
          tag: 'ಬೆಸ್ಕಾಂ / ಇಂಧನ',
        },
        {
          id: 'anna_bhagya',
          title: 'ಅನ್ನಭಾಗ್ಯ ಯೋಜನೆ (ಉಚಿತ ಅಕ್ಕಿ & DBT)',
          desc: 'ಬಿಪಿಎಲ್ ಕುಟುಂಬಗಳಿಗೆ ಉಚಿತ ಆಹಾರ ಧಾನ್ಯ ಮತ್ತು ನಗದು ವರ್ಗಾವಣೆ',
          query: 'ಅನ್ನಭಾಗ್ಯ ಯೋಜನೆಯ ಉಚಿತ ಅಕ್ಕಿ ಮತ್ತು ನೇರ ನಗದು ವರ್ಗಾವಣೆ ವಿವರ ತಿಳಿಸಿ.',
          icon: '🍚',
          tag: 'ಆಹಾರ ಇಲಾಖೆ',
        },
        {
          id: 'arogya',
          title: 'ಆರೋಗ್ಯ ಕರ್ನಾಟಕ (ಉಚಿತ ಚಿಕಿತ್ಸೆ)',
          desc: 'ಆಸ್ಪತ್ರೆಯಲ್ಲಿ ₹5 ಲಕ್ಷದವರೆಗೆ ಉಚಿತ ನಗದುರಹಿತ ಚಿಕಿತ್ಸೆ',
          query: 'ಆರೋಗ್ಯ ಕರ್ನಾಟಕ ಆಯುಷ್ಮಾನ್ ಭಾರತ್ ಯೋಜನೆಯಡಿ 5 ಲಕ್ಷ ರೂಪಾಯಿ ಉಚಿತ ಚಿಕಿತ್ಸೆ ಹೇಗೆ ಪಡೆಯುವುದು?',
          icon: '🏥',
          tag: 'ಆರೋಗ್ಯ ಇಲಾಖೆ',
        },
      ],
    },
    hi: {
      appName: 'आवाज़ सेतु',
      tagline: 'कर्नाटक नागरिक वॉयस सेवा',
      elderTip: 'वरिष्ठ नागरिकों के लिए आसान सेवा: बड़ा माइक दबाएं और सीधे बोलें।',
      langSelect: 'भाषा / Language:',
      youSaid: 'आपने पूछा:',
      govAnswer: 'सरकारी जवाब:',
      replay: 'दोबारा सुनें (Replay)',
      popularSchemes: 'प्रमुख सरकारी योजनाएं:',
      schemes: [
        {
          id: 'sandhya',
          title: 'संध्या सुरक्षा (पेंशन योजना)',
          desc: '65+ वरिष्ठ नागरिकों को ₹1,000/माह पेंशन',
          query: 'संध्या सुरक्षा योजना के तहत वरिष्ठ नागरिकों को 1000 रुपये पेंशन कैसे मिलती है?',
          icon: '👴',
          tag: 'DSSP पोर्टल',
        },
        {
          id: 'gruha_lakshmi',
          title: 'गृह लक्ष्मी योजना (₹2,000/माह)',
          desc: 'घर की मुखिया महिला को हर माह ₹2,000',
          query: 'गृह लक्ष्मी योजना का 2000 रुपये मासिक लाभ कैसे प्राप्त करें?',
          icon: '👵',
          tag: 'सेवा सिंधु',
        },
        {
          id: 'bhoomi',
          title: 'भूमि पोर्टल (जमीन आरटीसी / पहणी)',
          desc: 'कर्नाटक में जमीन रिकॉर्ड और पहणी डाउनलोड करें',
          query: 'भूमि पोर्टल से जमीन की आरटीसी पहणी कैसे डाउनलोड करें?',
          icon: '🌾',
          tag: 'भूमि पोर्टल',
        },
        {
          id: 'gruha_jyothi',
          title: 'गृह ज्योति (200 यूनिट मुफ्त बिजली)',
          desc: 'घरेलू उपयोग के लिए 200 यूनिट तक फ्री बिजली',
          query: 'गृह ज्योति योजना 200 यूनिट फ्री बिजली की पात्रता क्या है?',
          icon: '💡',
          tag: 'BESCOM पोर्टल',
        },
      ],
    },
  }[language] || {};

  return (
    <div className="flex flex-col h-full text-slate-100 justify-between select-none">
      {/* Phone App Top Header */}
      <div>
        <div className="flex items-center justify-between border-b border-slate-800 pb-2 mb-2">
          <div>
            <h1 className="text-base font-extrabold text-white flex items-center gap-1.5 tracking-tight">
              <span className="text-amber-400">🏛️</span> {content.appName}
            </h1>
            <p className="text-[10px] text-emerald-400 font-medium">
              {content.tagline}
            </p>
          </div>

          {/* Language Switcher for Senior Citizens */}
          <div className="flex items-center bg-slate-900 border border-slate-800 rounded-xl p-0.5 shadow-inner">
            <button
              type="button"
              onClick={() => setLanguage('en')}
              className={`text-[10px] px-2 py-1 rounded-lg font-bold transition-all ${
                language === 'en'
                  ? 'bg-emerald-500 text-slate-950 shadow'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              EN
            </button>
            <button
              type="button"
              onClick={() => setLanguage('kn')}
              className={`text-[10px] px-2 py-1 rounded-lg font-bold transition-all ${
                language === 'kn'
                  ? 'bg-emerald-500 text-slate-950 shadow'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              ಕನ್ನಡ
            </button>
            <button
              type="button"
              onClick={() => setLanguage('hi')}
              className={`text-[10px] px-2 py-1 rounded-lg font-bold transition-all ${
                language === 'hi'
                  ? 'bg-emerald-500 text-slate-950 shadow'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              हिंदी
            </button>
          </div>
        </div>

        {/* Friendly Guidance Banner for Old Age Users */}
        <div className="bg-emerald-950/40 border border-emerald-800/40 rounded-xl px-2.5 py-1.5 mb-2 flex items-center gap-2">
          <Heart className="w-4 h-4 text-rose-400 shrink-0" />
          <p className="text-[10px] text-emerald-200/90 leading-tight">
            {content.elderTip}
          </p>
        </div>

        {/* Tab Switcher: Voice Hub vs One-Touch Schemes */}
        <div className="grid grid-cols-2 gap-1.5 bg-slate-900/80 p-1 rounded-xl border border-slate-800 mb-2">
          <button
            type="button"
            onClick={() => setActiveTab('voice')}
            className={`py-1.5 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'voice'
                ? 'bg-slate-800 text-emerald-400 shadow'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Mic className="w-3.5 h-3.5 text-emerald-400" />
            <span>Google Voice Mic</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('schemes')}
            className={`py-1.5 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-1.5 ${
              activeTab === 'schemes'
                ? 'bg-slate-800 text-emerald-400 shadow'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Landmark className="w-3.5 h-3.5 text-amber-400" />
            <span>Gov Schemes</span>
          </button>
        </div>
      </div>

      {/* Main Tab 1: Google Voice Mic & Live Subtitles */}
      {activeTab === 'voice' && (
        <div className="flex-1 flex flex-col justify-between py-1">
          {/* Central Google Microphone with Voice Fluctuation Wave Bars */}
          <GoogleMicrophone
            isListening={isListening}
            isProcessing={isProcessing}
            isSpeaking={isSpeaking}
            volume={volume}
            barLevels={barLevels}
            onToggleListen={toggleListen}
            onStopSpeaking={stopSpeaking}
            language={language}
          />

          {/* Spoken Subtitles & Response Cards (High Readability for Elders) */}
          <div className="space-y-2 mt-2">
            {/* User's Spoken Query */}
            {userTranscript && (
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-2.5 shadow-sm">
                <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider block mb-0.5">
                  🗣️ {content.youSaid}
                </span>
                <p className="text-sm font-semibold text-emerald-300">
                  "{userTranscript}"
                </p>
              </div>
            )}

            {/* AI Spoken Answer Card */}
            {aiResponse && (
              <div className="bg-slate-900/90 border border-slate-800 rounded-xl p-2.5 shadow-md">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[10px] uppercase font-bold text-sky-400 flex items-center gap-1">
                    <Volume2 className="w-3 h-3 text-sky-400" />
                    {content.govAnswer}
                  </span>

                  {/* Replay Audio Button for Elders */}
                  <button
                    type="button"
                    onClick={replayAudio}
                    className="flex items-center gap-1 text-[10px] bg-slate-800 hover:bg-slate-700 text-slate-300 px-2 py-0.5 rounded-lg border border-slate-700"
                  >
                    <RotateCcw className="w-2.5 h-2.5 text-amber-400" />
                    <span>{content.replay}</span>
                  </button>
                </div>

                <p className="text-xs text-slate-200 leading-relaxed font-sans max-h-24 overflow-y-auto pr-1">
                  {aiResponse}
                </p>

                {dpiData?.source_url && (
                  <a
                    href={dpiData.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-2 inline-flex items-center gap-1 text-[10px] text-emerald-400 hover:underline font-semibold"
                  >
                    <ExternalLink className="w-3 h-3" />
                    <span>{dpiData.source_url.replace('https://', '')}</span>
                  </a>
                )}
              </div>
            )}

            {/* Error Notice */}
            {error && (
              <div className="bg-rose-950/60 border border-rose-800/80 rounded-xl p-2 text-center text-xs text-rose-300">
                {error}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Main Tab 2: One-Touch Welfare Schemes for Senior Citizens */}
      {activeTab === 'schemes' && (
        <div className="flex-1 flex flex-col justify-start overflow-y-auto py-1 pr-1 space-y-2">
          <p className="text-xs text-slate-400 font-semibold mb-1">
            {content.popularSchemes}
          </p>

          {content.schemes?.map((s) => (
            <button
              key={s.id}
              type="button"
              disabled={isProcessing}
              onClick={() => {
                setActiveTab('voice');
                executeQuery(s.query);
              }}
              className="w-full text-left bg-slate-900/90 hover:bg-emerald-950/50 border border-slate-800 hover:border-emerald-600/70 p-2.5 rounded-xl transition-all shadow-sm flex items-start gap-2.5 group disabled:opacity-50"
            >
              <span className="text-xl shrink-0 p-1 bg-slate-800 rounded-lg group-hover:scale-110 transition-transform">
                {s.icon}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-1">
                  <h3 className="text-xs font-bold text-white group-hover:text-emerald-300 truncate">
                    {s.title}
                  </h3>
                  <span className="text-[9px] bg-slate-800 text-slate-400 px-1.5 py-0.5 rounded border border-slate-700 shrink-0">
                    {s.tag}
                  </span>
                </div>
                <p className="text-[10px] text-slate-400 mt-0.5 line-clamp-1">
                  {s.desc}
                </p>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Bottom Phone Action Bar */}
      <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={onOpenDialer}
          className="flex-1 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition-all shadow border border-slate-700"
        >
          <Phone className="w-3.5 h-3.5 text-emerald-400" />
          <span>Virtual Dialer</span>
        </button>

        {isListening && (
          <button
            type="button"
            onClick={toggleListen}
            className="px-3 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-bold transition-all shadow"
          >
            Done Speaking
          </button>
        )}
      </div>
    </div>
  );
}

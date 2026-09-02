import React, { useState, useEffect, useRef } from 'react'
import { marked } from 'marked'
import Chart from 'react-apexcharts'
import {
  Brain,
  Send,
  Terminal,
  Play,
  TrendingUp,
  Newspaper,
  Activity,
  TrendingDown,
  Settings,
  X,
  RotateCcw,
  Sparkles,
  FileCode,
  ShieldCheck
} from 'lucide-react'

// Define typings
interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface AgentState {
  name: string
  role: string
  status: 'IDLE' | 'WORKING' | 'SUCCESS' | 'ERROR'
  color: string
}

interface Thought {
  agent: string
  text: string
  time: string
}

const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8000'
  : window.location.origin

// Available Python Templates
const PYTHON_TEMPLATES = [
  {
    name: 'Temel İnceleme',
    code: `# FinansAPI Python Code Interpreter (WebAssembly)
# Tarayıcıda yerel Python motoru ile analiz yapın!

import pandas as pd
import json

# Örnek BIST Verisi Yükleme ve İnceleme
symbol = "THYAO"
print(f"[{symbol}] Analiz Ediliyor...")

# Korelasyon veya istatistiksel işlemlerinizi burada yapabilirsiniz.
# Örneğin, son 12 ayın ortalama fiyatını ve volatiliteyi hesaplayalım:
fiyatlar = [305.5, 307.75, 310.2, 308.9, 312.4, 309.8, 314.0]
df = pd.Series(fiyatlar)

print("Son Fiyat Serisi (TL):")
print(df.to_string())
print(f"Ortalama Fiyat: {df.mean():.2f} TL")
print(f"Standart Sapma (Volatilite): {df.std():.2f} TL")
`
  },
  {
    name: 'Volatilite & Risk Analizi',
    code: `# Volatilite ve Risk Analizi Şablonu
import numpy as np
import pandas as pd

# Örnek günlük getiri yüzdeleri
gunluk_getiriler = np.random.normal(0.001, 0.015, 100)
df = pd.Series(gunluk_getiriler)

# Yıllıklandırılmış Volatilite (252 işlem günü)
yillik_volatilite = df.std() * np.sqrt(252) * 100
# Risk Altındaki Değer (Value at Risk - VaR %95 güven seviyesi)
var_95 = df.quantile(0.05) * 100

print("--- PORTFÖY RİSK ANALİZİ ---")
print(f"Toplam Analiz Edilen Gün: {len(df)}")
print(f"Yıllıklandırılmış Volatilite (Risk): %{yillik_volatilite:.2f}")
print(f"Günlük Maksimum Beklenen Kayıp (VaR %95): %{-var_95:.2f}")
`
  },
  {
    name: 'Monte Carlo Simülasyonu',
    code: `# Basit Monte Carlo Fiyat Projeksiyonu
import numpy as np

son_fiyat = 314.0
gunluk_oynaklik = 0.018 # %1.8 günlük oynaklık
gunler = 10
simulasyon_sayisi = 5

print(f"Mevcut Fiyat: {son_fiyat} TL")
print(f"{gunler} Günlük Monte Carlo Projeksiyonları:")

for i in range(simulasyon_sayisi):
    fiyat_yolu = [son_fiyat]
    for _ in range(gunler):
        şok = np.random.normal(0, gunluk_oynaklik)
        yeni_fiyat = fiyat_yolu[-1] * (1 + şok)
        fiyat_yolu.append(yeni_fiyat)
    print(f"Simülasyon #{i+1}: {fiyat_yolu[-1]:.2f} TL")
`
  }
]

export default function App() {
  // Chat History persistence in localStorage
  const [messages, setMessages] = useState<Message[]>(() => {
    const saved = localStorage.getItem('finansapi_chat_messages') || localStorage.getItem('borsapy_chat_messages')
    if (saved) {
      try {
        return JSON.parse(saved)
      } catch (e) {
        // Fallback
      }
    }
    return [
      {
        role: 'assistant',
        content: 'Merhaba! FinansAPI Çoklu Ajan Analiz Odasına hoş geldiniz. Hangi hisse senedi veya fon hakkında analiz yapmak istersiniz? (Örn: "THYAO teknik analizi nasıldır?" veya "Son borsa haberleri neler?")'
      }
    ]
  })

  // Settings states stored in localStorage
  const [apiKey, setApiKey] = useState(() => localStorage.getItem('finansapi_api_key') || localStorage.getItem('borsapy_api_key') || '')
  const [provider, setProvider] = useState(() => localStorage.getItem('finansapi_provider') || localStorage.getItem('borsapy_provider') || 'openai')
  const [customModel, setCustomModel] = useState(() => localStorage.getItem('finansapi_model') || localStorage.getItem('borsapy_model') || 'gpt-4.1-mini')
  const [isSettingsOpen, setIsSettingsOpen] = useState(false)

  const [input, setInput] = useState('')
  const [symbol, setSymbol] = useState('THYAO')
  const [activeTab, setActiveTab] = useState<'market' | 'analytics' | 'python'>('market')
  const [isLoading, setIsLoading] = useState(false)

  // Market states
  const [marketSummary, setMarketSummary] = useState<any>(null)
  const [marketNews, setMarketNews] = useState<any[]>([])

  // Analytics states
  const [stockDetail, setStockDetail] = useState<any>(null)
  const [stockHistory, setStockHistory] = useState<any[]>([])
  const [stockRecommendations, setStockRecommendations] = useState<any>(null)
  const [stockHolders, setStockHolders] = useState<any[]>([])
  const [stockEtfs, setStockEtfs] = useState<any[]>([])
  const [stockCalendar, setStockCalendar] = useState<any>(null)

  // Python state
  const [pythonCode, setPythonCode] = useState<string>(PYTHON_TEMPLATES[0].code)
  const [pythonOutput, setPythonOutput] = useState<string>('Python motoru yükleniyor...')
  const [pyodideInstance, setPyodideInstance] = useState<any>(null)

  // Agent States
  const [agents, setAgents] = useState<AgentState[]>([
    { name: 'Orkestratör', role: 'Koordinatör Ajan', status: 'IDLE', color: 'border-cyan-500/30 text-cyan-400 bg-cyan-950/20' },
    { name: 'Teknik Ajan', role: 'Göstergeler & Sinyaller', status: 'IDLE', color: 'border-purple-500/30 text-purple-400 bg-purple-950/20' },
    { name: 'Temel Ajan', role: 'Bilanço & Değerleme', status: 'IDLE', color: 'border-emerald-500/30 text-emerald-400 bg-emerald-950/20' },
    { name: 'Haber & Makro', role: 'Haberler & Enflasyon', status: 'IDLE', color: 'border-amber-500/30 text-amber-400 bg-amber-950/20' },
    { name: 'Python Ajanı', role: 'Kod & Matematik', status: 'IDLE', color: 'border-rose-500/30 text-rose-400 bg-rose-950/20' }
  ])

  const [thoughts, setThoughts] = useState<Thought[]>([
    { agent: 'Orkestratör', text: 'Analiz odası hazır. İstek bekleniyor...', time: '14:50' }
  ])

  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Sync messages to local storage
  useEffect(() => {
    localStorage.setItem('finansapi_chat_messages', JSON.stringify(messages))
  }, [messages])

  // Sync settings to local storage automatically
  useEffect(() => {
    localStorage.setItem('finansapi_api_key', apiKey)
    localStorage.setItem('finansapi_provider', provider)
    localStorage.setItem('finansapi_model', customModel)
  }, [apiKey, provider, customModel])

  // Save Settings to local storage
  const saveSettings = (key: string, prov: string, model: string) => {
    localStorage.setItem('finansapi_api_key', key)
    localStorage.setItem('finansapi_provider', prov)
    localStorage.setItem('finansapi_model', model)
    setApiKey(key)
    setProvider(prov)
    setCustomModel(model)
    setIsSettingsOpen(false)
  }

  const clearChat = () => {
    if (window.confirm('Mesaj geçmişini temizlemek istediğinize emin misiniz?')) {
      setMessages([
        {
          role: 'assistant',
          content: 'Merhaba! FinansAPI Çoklu Ajan Analiz Odasına hoş geldiniz. Hangi hisse senedi veya fon hakkında analiz yapmak istersiniz?'
        }
      ])
    }
  }

  // Initialize Pyodide
  useEffect(() => {
    const initPyodide = async () => {
      try {
        if (!(window as any).loadPyodide) {
          const script = document.createElement('script')
          script.src = 'https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js'
          script.async = true
          script.onload = async () => {
            const pyo = await (window as any).loadPyodide()
            await pyo.loadPackage(['pandas', 'numpy'])
            setPyodideInstance(pyo)
            setPythonOutput('Python motoru (Pyodide Wasm) başarıyla yüklendi! Çalıştırmaya hazır.')
          }
          document.head.appendChild(script)
        } else {
          const pyo = await (window as any).loadPyodide()
          await pyo.loadPackage(['pandas', 'numpy'])
          setPyodideInstance(pyo)
          setPythonOutput('Python motoru (Pyodide Wasm) başarıyla yüklendi! Çalıştırmaya hazır.')
        }
      } catch (err) {
        setPythonOutput('Python motoru yüklenirken hata oluştu.')
        console.error(err)
      }
    }
    initPyodide()
  }, [])

  // Load General Market Data on startup
  useEffect(() => {
    fetchMarketData()
    fetchStockData(symbol)
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thoughts])

  const fetchMarketData = async () => {
    try {
      const [sumRes, newsRes] = await Promise.all([
        fetch(`${API_BASE}/market/summary`),
        fetch(`${API_BASE}/market/news`)
      ])
      if (sumRes.ok) {
        const sumData = await sumRes.json()
        setMarketSummary(sumData.data)
      }
      if (newsRes.ok) {
        const newsData = await newsRes.json()
        setMarketNews(newsData)
      }
    } catch (e) {
      console.error(e)
    }
  }

  const fetchStockData = async (targetSymbol: string) => {
    const sym = targetSymbol.toUpperCase().trim()
    if (!sym) return false
    
    // Detect type based on length: 3 letters is TEFAS fund, 4-5 letters is BIST stock
    const isFund = sym.length === 3
    
    try {
      if (isFund) {
        const detailRes = await fetch(`${API_BASE}/funds/${sym}`)
        if (!detailRes.ok) return false
        
        const detailData = await detailRes.json()
        
        // Fetch history and estimated return/allocation
        const [histRes, estRes] = await Promise.all([
          fetch(`${API_BASE}/funds/${sym}/history?period=3mo`),
          fetch(`${API_BASE}/funds/${sym}/estimated-return`)
        ])
        
        // Map fund details to stockDetail shape for UI compatibility
        const fundInfo = detailData
        setStockDetail({
          symbol: sym,
          longName: fundInfo.name || 'TEFAS Yatırım Fonu',
          last_price: fundInfo.price || 0,
          category: fundInfo.category,
          risk_value: fundInfo.risk_value,
          isFund: true
        })
        
        if (histRes.ok) {
          const histData = await histRes.json()
          // Map to chart shape: usually has Close/price
          setStockHistory((histData || []).map((h: any) => ({
            Date: h.Date || h.date || h.tarih || '',
            Close: h.Price || h.price || h.Close || 0
          })))
        } else {
          setStockHistory([])
        }
        
        setStockRecommendations(null)
        
        if (estRes.ok) {
          const estData = await estRes.json()
          // Map breakdown/allocation to holders shape to show asset distribution
          setStockHolders((estData.breakdown || []).map((b: any) => ({
            Holder: b.asset || 'Varlık',
            Percentage: b.weight || 0
          })))
        } else {
          setStockHolders([])
        }
        
        setStockEtfs([])
        setStockCalendar(null)
        return true
      } else {
        const detailRes = await fetch(`${API_BASE}/stocks/${sym}`)
        if (!detailRes.ok) return false
        
        const detailData = await detailRes.json()
        
        const [histRes, recRes, holdRes, etfRes, calRes] = await Promise.all([
          fetch(`${API_BASE}/stocks/${sym}/history?period=3mo&interval=1d`),
          fetch(`${API_BASE}/stocks/${sym}/recommendations`),
          fetch(`${API_BASE}/stocks/${sym}/holders`),
          fetch(`${API_BASE}/stocks/${sym}/etfs`),
          fetch(`${API_BASE}/stocks/${sym}/calendar`)
        ])
        
        setStockDetail({
          ...detailData.data,
          isFund: false
        })
        
        if (histRes.ok) setStockHistory(await histRes.json())
        else setStockHistory([])
        
        if (recRes.ok) setStockRecommendations(await recRes.json())
        else setStockRecommendations(null)
        
        if (holdRes.ok) setStockHolders(await holdRes.json())
        else setStockHolders([])
        
        if (etfRes.ok) setStockEtfs(await etfRes.json())
        else setStockEtfs([])
        
        if (calRes.ok) setStockCalendar(await calRes.json())
        else setStockCalendar(null)
        
        return true
      }
    } catch (e) {
      console.error(e)
      return false
    }
  }


  const runPython = async () => {
    if (!pyodideInstance) {
      alert('Python motoru henüz yüklenmedi, lütfen birkaç saniye bekleyin.')
      return
    }
    setPythonOutput('Çalıştırılıyor...\n')
    try {
      pyodideInstance.runPython(`
import sys
import io
sys.stdout = io.StringIO()
sys.stderr = io.StringIO()
`)
      await pyodideInstance.runPythonAsync(pythonCode)
      const stdout = pyodideInstance.runPython('sys.stdout.getvalue()')
      const stderr = pyodideInstance.runPython('sys.stderr.getvalue()')
      setPythonOutput((stdout || '') + (stderr || ''))
    } catch (err: any) {
      setPythonOutput('Hata:\n' + err.message)
    }
  }

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim()) return

    const userMsg = input
    setInput('')
    const updatedMessages = [...messages, { role: 'user', content: userMsg } as Message]
    setMessages(updatedMessages)
    setIsLoading(true)

    // Parse symbol if present in query (e.g. THYAO, MAC)
    const normalizedUserMsg = userMsg.toLocaleUpperCase('tr-TR')
    const matchedSymbolMatch = normalizedUserMsg.match(/\b([A-ZÇĞİÖŞÜ]{3,5})\b/)
    const parsedSymbol = matchedSymbolMatch ? matchedSymbolMatch[0] : null
    
    const BLACKLIST = [
      'BEN', 'SEN', 'TEK', 'BİR', 'HER', 'İLE', 'VE', 'DE', 'DA', 'KAP', 
      'FON', 'FONA', 'FONU', 'HANGİ', 'HANGI', 'MODEL', 'ANALİZ', 'ANALIZ', 'TEST', 'NEDİR', 'NEDIR', 'NASIL', 'NEDEN', 
      'BUGÜN', 'YARIN', 'ŞİMDİ', 'HAYIR', 'EVET', 'YAPAY', 'ZEKA', 'HİSSE', 'GÖRE', 'BANA', 'SANA', 'ONU', 'BUNU', 'ŞUNU', 'İÇİN', 'ICIN',
      'TABLO', 'KOD', 'YAZ', 'OKU', 'BAK', 'BUL', 'GETİR', 'GETIR', 'VER', 'AMA', 'HER', 'ÇOK', 'YOK', 'VAR', 'BİZ'
    ]
    
    const targetSymbol = parsedSymbol && !BLACKLIST.includes(parsedSymbol) ? parsedSymbol : null

    if (targetSymbol && targetSymbol !== symbol) {
      const success = await fetchStockData(targetSymbol)
      if (success) {
        setSymbol(targetSymbol)
      }
    }

    // Make backend AI call
    try {
      const headers: Record<string, string> = { 'Content-Type': 'application/json' }
      
      if (apiKey) {
        headers['X-AI-Key'] = apiKey
        headers['X-AI-Provider'] = provider
        headers['X-AI-Model'] = customModel
      }

      // 1. Detect Intent: Check if the user query is a financial analysis query or general conversation
      const queryLower = userMsg.toLowerCase()
      const hasSymbol = !!targetSymbol
      
      // Keywords mapping to identify which specific agent should be activated
      const needsTechnical = ['grafik', 'rsi', 'macd', 'ortalama', 'sma', 'ema', 'teknik', 'destek', 'direnç', 'sinyal', 'trend'].some(k => queryLower.includes(k))
      const needsFundamental = ['bilanço', 'fk', 'f/k', 'pddd', 'pd/dd', 'gelir', 'temel', 'kar', 'kâr', 'ortak', 'etf', 'hissedar', 'holder'].some(k => queryLower.includes(k))
      const needsMacroNews = ['kap', 'haber', 'ekonomik', 'faiz', 'enflasyon', 'tcmb', 'takvim', 'makro', 'duyuru'].some(k => queryLower.includes(k))
      const needsPython = ['kod', 'simülasyon', 'hesapla', 'python', 'monte', 'carlo', 'var', 'volatilite', 'formül'].some(k => queryLower.includes(k))

      const isFinancialQuery = hasSymbol || needsTechnical || needsFundamental || needsMacroNews || needsPython

      if (isFinancialQuery) {
        setThoughts([])
        
        // Helper to delay and log thought
        const addThought = (agent: string, text: string, delay: number) => {
          return new Promise<void>(resolve => {
            setTimeout(() => {
              setThoughts(prev => [...prev, { agent, text, time: new Date().toLocaleTimeString().slice(0, 5) }])
              setAgents(prev => prev.map(a => a.name === agent ? { ...a, status: 'WORKING' } : a))
              resolve()
            }, delay)
          })
        }

        const setAgentSuccess = (agent: string, delay: number) => {
          return new Promise<void>(resolve => {
            setTimeout(() => {
              setAgents(prev => prev.map(a => a.name === agent ? { ...a, status: 'SUCCESS' } : a))
              resolve()
            }, delay)
          })
        }

        // Determine what name to print in thought logs (use symbol if explicitly matched in current message, else default to "Piyasa")
        const subjectName = targetSymbol ? targetSymbol : "Piyasa"

        // Always activate orchestrator
        await addThought('Orkestratör', `${subjectName} analizi görevi alındı. İlgili uzman ajanlar koordine ediliyor...`, 100)

        // If specific keywords exist, run only that agent. If general financial analysis (like just "THYAO analizi"), activate all relevant ones.
        const isGeneralFinancial = (hasSymbol || queryLower.includes('analiz') || queryLower.includes('piyasa')) && !needsTechnical && !needsFundamental && !needsMacroNews && !needsPython

        if (needsTechnical || isGeneralFinancial) {
          await addThought('Teknik Ajan', `${subjectName} teknik indikatörleri ve sinyalleri analiz ediliyor...`, 400)
          await setAgentSuccess('Teknik Ajan', 100)
        }
        
        if (needsFundamental || isGeneralFinancial) {
          await addThought('Temel Ajan', `${subjectName} bilanço rasyoları ve ortaklık yapısı inceleniyor...`, 400)
          await setAgentSuccess('Temel Ajan', 100)
        }

        if (needsMacroNews || isGeneralFinancial) {
          await addThought('Haber & Makro', `${subjectName} güncel haber sentimenti ve KAP akışı taranıyor...`, 400)
          await setAgentSuccess('Haber & Makro', 100)
        }

        if (needsPython || isGeneralFinancial) {
          await addThought('Python Ajanı', 'İstatisksel formüller ve hesaplamalar çalıştırılıyor...', 400)
          await setAgentSuccess('Python Ajanı', 100)
        }

        await addThought('Orkestratör', 'Gerekli uzman analizleri tamamlandı. Rapor birleştiriliyor...', 200)
        await setAgentSuccess('Orkestratör', 50)
      } else {
        // General query: Only orchestrator answers without calling agents
        setThoughts([
          { agent: 'Orkestratör', text: 'Genel konuşma/soru algılandı. Uzman finans ajanlarına gerek duyulmadan doğrudan yanıt veriliyor.', time: new Date().toLocaleTimeString().slice(0, 5) }
        ])
        setAgents(prev => prev.map(a => a.name === 'Orkestratör' ? { ...a, status: 'WORKING' } : a))
        await new Promise(r => setTimeout(r, 400))
        setAgents(prev => prev.map(a => a.name === 'Orkestratör' ? { ...a, status: 'SUCCESS' } : a))
      }

      const res = await fetch(`${API_BASE}/ai/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          messages: updatedMessages.slice(-6)
        })
      })

      if (res.ok) {
        const data = await res.json()
        // Safe access: check for error response or missing choices
        if (data.error) {
          setMessages(prev => [...prev, { role: 'assistant', content: `⚠️ ${data.error}` }])
        } else if (data.choices && data.choices[0]?.message?.content) {
          setMessages(prev => [...prev, { role: 'assistant', content: data.choices[0].message.content }])
        } else {
          setMessages(prev => [...prev, { role: 'assistant', content: 'Yanıt alınamadı. Lütfen tekrar deneyin.' }])
        }
      } else {
        let errMsg = 'Üzgünüm, API bağlantısı kurulamadı.'
        try {
          const errData = await res.json()
          if (errData && errData.detail) {
            errMsg = errData.detail
          }
        } catch (e) {
          // Fallback
        }
        setMessages(prev => [...prev, { role: 'assistant', content: errMsg }])
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Bağlantı hatası oluştu.' }])
    } finally {
      setIsLoading(false)
      setTimeout(() => {
        setAgents(prev => prev.map(a => ({ ...a, status: 'IDLE' })))
      }, 2000)
    }
  }

  // Chart options formatting
  const chartSeries = [
    {
      name: 'Fiyat',
      data: stockHistory.map(h => h.Close || h.close || h.price || 0)
    }
  ]

  const chartOptions: ApexCharts.ApexOptions = {
    chart: {
      type: 'line',
      toolbar: { show: false },
      background: 'transparent'
    },
    colors: ['#a855f7'],
    stroke: { curve: 'smooth', width: 2 },
    grid: { borderColor: '#1f2937' },
    xaxis: {
      categories: stockHistory.map(h => {
        const dateVal = h.Date || h.date || h.tarih || ''
        return dateVal ? dateVal.split('T')[0] : ''
      }),
      labels: { style: { colors: '#9ca3af' } }
    },
    yaxis: {
      labels: { style: { colors: '#9ca3af' } }
    },
    theme: { mode: 'dark' }
  }

  const renderMarkdown = (text: string) => {
    try {
      const rawHtml = marked.parse(text, { async: false }) as string
      // Sanitize HTML to prevent XSS from AI-generated content
      const purify = (window as any).DOMPurify
      if (purify) {
        return { __html: purify.sanitize(rawHtml) }
      }
      return { __html: rawHtml }
    } catch (e) {
      return { __html: text }
    }
  }

  return (
    <div className="flex flex-col lg:flex-row h-screen bg-neutral-950 text-neutral-200 overflow-hidden font-sans">
      
      {/* LEFT PANEL: Multi-Agent Monitor */}
      <div className="w-full lg:w-80 bg-neutral-900 border-b lg:border-b-0 lg:border-r border-neutral-800 flex flex-col p-4 shrink-0">
        <div className="flex items-center justify-between mb-6 border-b border-neutral-800 pb-4">
          <div className="flex items-center gap-2">
            <Brain className="w-6 h-6 text-purple-400 animate-pulse" />
            <div>
              <div className="flex items-center gap-1.5">
                <h1 className="text-lg font-bold text-white tracking-tight">FinansAPI</h1>
                <span className="text-[10px] font-mono bg-purple-900/60 text-purple-300 border border-purple-700/60 px-1.5 py-0.5 rounded font-bold">v3</span>
              </div>
              <p className="text-xs text-neutral-400">Çoklu Ajan Kontrol Odası</p>
            </div>
          </div>
          <button 
            onClick={() => setIsSettingsOpen(true)}
            className="p-1.5 rounded-lg hover:bg-neutral-800 text-neutral-400 hover:text-white transition-colors border border-neutral-800"
            title="Bağlantı Ayarları"
          >
            <Settings className="w-4 h-4" />
          </button>
        </div>

        {/* Agents List */}
        <div className="flex flex-col gap-3 mb-6">
          <h2 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-1">Aktif Ajan Ağı</h2>
          {agents.map((agent, i) => (
            <div key={i} className={`flex items-center justify-between p-3 border rounded-xl transition-all duration-300 ${agent.color}`}>
              <div>
                <p className="text-sm font-semibold text-white">{agent.name}</p>
                <p className="text-xs opacity-75">{agent.role}</p>
              </div>
              <div className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${agent.status === 'WORKING' ? 'bg-amber-400 animate-ping' : agent.status === 'SUCCESS' ? 'bg-emerald-400' : 'bg-neutral-600'}`} />
                <span className="text-[10px] font-mono tracking-wider">{agent.status}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Live Thoughts Logger */}
        <div className="flex-1 flex flex-col overflow-hidden">
          <h2 className="text-xs font-semibold text-neutral-500 uppercase tracking-wider mb-2">Ajan Düşünce Akışı</h2>
          <div className="flex-1 overflow-y-auto bg-neutral-950 rounded-xl p-3 border border-neutral-800 font-mono text-[11px] leading-relaxed flex flex-col gap-2.5">
            {thoughts.map((thought, i) => (
              <div key={i} className="border-l-2 border-neutral-700 pl-2 py-0.5">
                <span className="text-purple-400 font-bold">{thought.agent}</span>
                <span className="text-neutral-500 text-[9px] ml-1.5">{thought.time}</span>
                <p className="text-neutral-300 mt-0.5">{thought.text}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* CENTER PANEL: Chat Window */}
      <div className="flex-1 flex flex-col bg-neutral-950 border-b lg:border-b-0 lg:border-r border-neutral-800 h-[50vh] lg:h-auto overflow-hidden">
        {/* Header */}
        <div className="p-4 border-b border-neutral-800 flex items-center justify-between bg-neutral-900/40">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-full bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-400 font-bold">
              AI
            </div>
            <div>
              <h2 className="text-sm font-semibold text-white">FinansAPI Asistan</h2>
              <p className="text-xs text-neutral-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /> Orkestratör Ajan Aktif
              </p>
            </div>
          </div>
          <div className="flex gap-2 items-center">
            {apiKey && (
              <span className="text-[10px] bg-emerald-950 text-emerald-400 border border-emerald-800 px-2 py-1 rounded-md flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5" /> API Aktif
              </span>
            )}
            <button 
              onClick={clearChat}
              className="p-1 rounded-md hover:bg-neutral-800 text-neutral-400 hover:text-white transition-colors"
              title="Sohbeti Sıfırla"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
            <span className="text-xs bg-neutral-800 px-2 py-1 rounded-md border border-neutral-700">BIST</span>
          </div>
        </div>

        {/* Message Thread */}
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 max-w-[85%] ${msg.role === 'user' ? 'ml-auto flex-row-reverse' : ''}`}>
              <div className={`w-8 h-8 rounded-full shrink-0 flex items-center justify-center font-bold text-xs ${msg.role === 'user' ? 'bg-neutral-800 text-white' : 'bg-purple-600/20 text-purple-400 border border-purple-500/30'}`}>
                {msg.role === 'user' ? 'U' : 'A'}
              </div>
              <div 
                className={`p-3.5 rounded-2xl leading-relaxed border chat-markdown ${msg.role === 'user' ? 'bg-neutral-900 border-neutral-800 text-neutral-100 rounded-tr-none' : 'bg-neutral-900/30 border-neutral-800 text-neutral-200 rounded-tl-none'}`}
                dangerouslySetInnerHTML={renderMarkdown(msg.content)}
              />
            </div>
          ))}
          {isLoading && (
            <div className="flex gap-3 max-w-[85%]">
              <div className="w-8 h-8 rounded-full shrink-0 bg-purple-600/20 text-purple-400 border border-purple-500/30 flex items-center justify-center font-bold text-xs">
                A
              </div>
              <div className="p-3.5 rounded-2xl bg-neutral-900/30 border border-neutral-800 text-neutral-400 text-sm flex items-center gap-2">
                <Activity className="w-4 h-4 animate-spin text-purple-400" /> Ajanlar analiz hazırlıyor...
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Chat Input */}
        <form onSubmit={handleSendMessage} className="p-4 border-t border-neutral-800 bg-neutral-900/20">
          <div className="flex gap-2">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Sorunuzu yazın (Örn: ASELS son haberleri analiz et...)"
              className="flex-1 bg-neutral-900 border border-neutral-800 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors"
            />
            <button type="submit" className="bg-purple-600 hover:bg-purple-500 text-white font-semibold rounded-xl px-5 flex items-center justify-center transition-colors">
              <Send className="w-4 h-4" />
            </button>
          </div>
        </form>
      </div>

      {/* RIGHT PANEL: Dynamic Workspace (Tab-based) */}
      <div className="flex-1 flex flex-col bg-neutral-900/30 overflow-hidden h-[50vh] lg:h-auto">
        {/* Navigation Tabs */}
        <div className="flex border-b border-neutral-800 bg-neutral-900/40">
          <button
            onClick={() => setActiveTab('market')}
            className={`flex-1 py-3 text-xs font-semibold flex items-center justify-center gap-2 border-b-2 transition-all ${activeTab === 'market' ? 'border-purple-500 text-purple-400 bg-neutral-900/60' : 'border-transparent text-neutral-400'}`}
          >
            <Newspaper className="w-4 h-4" /> Genel Piyasa
          </button>
          <button
            onClick={() => setActiveTab('analytics')}
            className={`flex-1 py-3 text-xs font-semibold flex items-center justify-center gap-2 border-b-2 transition-all ${activeTab === 'analytics' ? 'border-purple-500 text-purple-400 bg-neutral-900/60' : 'border-transparent text-neutral-400'}`}
          >
            <TrendingUp className="w-4 h-4" /> {stockDetail?.isFund ? 'Fon Detay' : 'Hisse Detay'} ({symbol})
          </button>
          <button
            onClick={() => setActiveTab('python')}
            className={`flex-1 py-3 text-xs font-semibold flex items-center justify-center gap-2 border-b-2 transition-all ${activeTab === 'python' ? 'border-purple-500 text-purple-400 bg-neutral-900/60' : 'border-transparent text-neutral-400'}`}
          >
            <Terminal className="w-4 h-4" /> Python Konsolu
          </button>
        </div>

        {/* Tab Contents */}
        <div className="flex-1 overflow-y-auto p-4">
          
          {/* TAB 1: Market summary */}
          {activeTab === 'market' && (
            <div className="flex flex-col gap-4">
              {/* Market Breadth */}
              {marketSummary && (
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-neutral-900/40 p-4 border border-neutral-800 rounded-2xl text-center">
                    <p className="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-1">Yükselen</p>
                    <p className="text-xl font-bold text-emerald-400 flex items-center justify-center gap-1"><TrendingUp className="w-5 h-5"/>{marketSummary.breadth?.up || 0}</p>
                  </div>
                  <div className="bg-neutral-900/40 p-4 border border-neutral-800 rounded-2xl text-center">
                    <p className="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-1">Düşen</p>
                    <p className="text-xl font-bold text-rose-400 flex items-center justify-center gap-1"><TrendingDown className="w-5 h-5"/>{marketSummary.breadth?.down || 0}</p>
                  </div>
                  <div className="bg-neutral-900/40 p-4 border border-neutral-800 rounded-2xl text-center">
                    <p className="text-xs text-neutral-500 font-medium uppercase tracking-wider mb-1">Yatay</p>
                    <p className="text-xl font-bold text-neutral-400">{marketSummary.breadth?.neutral || 0}</p>
                  </div>
                </div>
              )}

              {/* News list */}
              <div className="bg-neutral-900/40 border border-neutral-800 rounded-2xl p-4">
                <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2 border-b border-neutral-800 pb-2">
                  <Newspaper className="w-4 h-4 text-purple-400" /> Son Finansal Haberler
                </h3>
                <div className="flex flex-col gap-3">
                  {marketNews.length > 0 ? (
                    marketNews.map((item, i) => (
                      <a key={i} href={item.link} target="_blank" rel="noreferrer" className="block p-3 bg-neutral-950/40 border border-neutral-800/60 rounded-xl hover:border-purple-500/50 transition-colors">
                        <div className="flex justify-between items-center gap-2 mb-1">
                          <span className="text-[10px] bg-purple-500/10 border border-purple-500/30 text-purple-400 px-1.5 py-0.5 rounded-md font-semibold">{item.source}</span>
                          <span className="text-[9px] text-neutral-500">{item.date}</span>
                        </div>
                        <h4 className="text-xs font-semibold text-neutral-200 line-clamp-1">{item.title}</h4>
                        <p className="text-[10px] text-neutral-400 mt-1 line-clamp-2">{item.summary}</p>
                      </a>
                    ))
                  ) : (
                    <p className="text-xs text-neutral-500 text-center py-4">Haberler yükleniyor...</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: Stock specific analytics */}
          {activeTab === 'analytics' && (
            <div className="flex flex-col gap-4">
              
              {/* Header Info */}
              {stockDetail && (
                <div className="bg-neutral-900/40 p-4 border border-neutral-800 rounded-2xl flex justify-between items-center">
                  <div>
                    <h3 className="text-lg font-bold text-white tracking-tight">{symbol}</h3>
                    <p className="text-xs text-neutral-400">
                      {stockDetail.isFund 
                        ? (stockDetail.category ? `TEFAS Fonu (${stockDetail.category})` : 'TEFAS Yatırım Fonu')
                        : (stockDetail.longName || 'BIST Hisse Senedi')}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-xl font-bold text-white">₺{(stockHistory[stockHistory.length - 1]?.Close || stockDetail.last_price || 0).toFixed(2)}</p>
                    <span className="text-xs bg-purple-500/10 text-purple-400 border border-purple-500/20 px-2 py-0.5 rounded-md">
                      {stockDetail.isFund ? 'TEFAS' : 'BIST'}
                    </span>
                  </div>
                </div>
              )}

              {/* Chart */}
              <div className="bg-neutral-900/40 p-4 border border-neutral-800 rounded-2xl">
                <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2">Fiyat Grafiği (Son 3 Ay)</h4>
                <div className="h-64">
                  {stockHistory.length > 0 ? (
                    <Chart options={chartOptions} series={chartSeries} type="line" height="100%" />
                  ) : (
                    <p className="text-xs text-neutral-500 text-center py-20">Grafik yükleniyor...</p>
                  )}
                </div>
              </div>

              {/* Recommendations */}
              {!stockDetail?.isFund && stockRecommendations?.targets && (
                <div className="bg-neutral-900/40 p-4 border border-neutral-800 rounded-2xl">
                  <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-3">Analist Hedef Fiyatları</h4>
                  <div className="grid grid-cols-3 gap-2 text-center mb-3">
                    <div className="p-2 bg-neutral-950 rounded-xl">
                      <p className="text-[10px] text-neutral-500">Ortalama Hedef</p>
                      <p className="text-sm font-semibold text-white">₺{stockRecommendations.targets.mean || '-'}</p>
                    </div>
                    <div className="p-2 bg-neutral-950 rounded-xl">
                      <p className="text-[10px] text-neutral-500">En Yüksek</p>
                      <p className="text-sm font-semibold text-white">₺{stockRecommendations.targets.high || '-'}</p>
                    </div>
                    <div className="p-2 bg-neutral-950 rounded-xl">
                      <p className="text-[10px] text-neutral-500">Analist Sayısı</p>
                      <p className="text-sm font-semibold text-white">{stockRecommendations.targets.numberOfAnalysts || '-'}</p>
                    </div>
                  </div>
                </div>
              )}

              {/* Major Holders */}
              {stockHolders.length > 0 && (
                <div className="bg-neutral-900/40 p-4 border border-neutral-800 rounded-2xl">
                  <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2">
                    {stockDetail?.isFund ? 'Fon Portföy / Varlık Dağılımı' : 'Büyük Ortaklık Yapısı'}
                  </h4>

                  <div className="flex flex-col gap-2">
                    {stockHolders.map((holder, i) => (
                      <div key={i} className="flex justify-between items-center p-2.5 bg-neutral-950 rounded-xl text-xs">
                        <span className="font-semibold text-neutral-300">{holder.Holder || holder.holder || 'Hissedar'}</span>
                        <span className="text-purple-400 font-bold">%{holder.Percentage || holder.percentage || 0}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ETF Holders */}
              {!stockDetail?.isFund && stockEtfs.length > 0 && (
                <div className="bg-neutral-900/40 p-4 border border-neutral-800 rounded-2xl">
                  <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2">Uluslararası ETF Sahipleri</h4>
                  <div className="flex flex-col gap-2">
                    {stockEtfs.slice(0, 5).map((etf, i) => (
                      <div key={i} className="flex justify-between items-center p-2.5 bg-neutral-950 rounded-xl text-xs">
                        <div>
                          <span className="font-semibold text-white">{etf.symbol || 'ETF'}</span>
                          <span className="text-[10px] text-neutral-400 block">{etf.name}</span>
                        </div>
                        <span className="text-purple-400 font-bold">%{((etf.holding_weight_pct || 0) * 100).toFixed(2)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Calendar / Earnings dates */}
              {!stockDetail?.isFund && stockCalendar && (stockCalendar.earnings_dates?.length > 0 || stockCalendar.calendar?.length > 0) && (
                <div className="bg-neutral-900/40 p-4 border border-neutral-800 rounded-2xl">
                  <h4 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2">Beklenen Bilanço Takvimi</h4>
                  <div className="flex flex-col gap-2">
                    {(stockCalendar.calendar || []).slice(0, 2).map((cal: any, i: number) => (
                      <div key={i} className="flex justify-between items-center p-2.5 bg-neutral-950 rounded-xl text-xs">
                        <div>
                          <span className="font-semibold text-neutral-300">{cal.Subject || 'Rapor'}</span>
                          <span className="text-[10px] text-neutral-500 block">{cal.Period} {cal.Year}</span>
                        </div>
                        <span className="text-neutral-400 font-semibold">{cal.EndDate || cal.StartDate}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* TAB 3: Pyodide WebAssembly Python Code Interpreter */}
          {activeTab === 'python' && (
            <div className="flex flex-col gap-4 h-full">
              {/* Ready templates selection */}
              <div className="flex items-center gap-2 bg-neutral-900/40 border border-neutral-800 p-3 rounded-2xl">
                <FileCode className="w-4 h-4 text-purple-400 shrink-0" />
                <span className="text-xs text-neutral-400 mr-2">Hazır Şablonlar:</span>
                <div className="flex gap-2 flex-wrap">
                  {PYTHON_TEMPLATES.map((tmpl, idx) => (
                    <button
                      key={idx}
                      onClick={() => setPythonCode(tmpl.code)}
                      className="text-[10px] bg-neutral-800 hover:bg-purple-950/40 hover:text-purple-400 border border-neutral-700 hover:border-purple-800 px-2 py-1 rounded transition-colors"
                    >
                      {tmpl.name}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex-1 bg-neutral-900 border border-neutral-800 rounded-2xl p-4 flex flex-col gap-3">
                <div className="flex items-center justify-between border-b border-neutral-800 pb-2">
                  <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider">Python Kod Editörü</h3>
                  <button onClick={runPython} className="bg-purple-600 hover:bg-purple-500 text-white font-semibold text-xs px-3.5 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors">
                    <Play className="w-3.5 h-3.5" /> Kodu Çalıştır
                  </button>
                </div>
                <textarea
                  value={pythonCode}
                  onChange={e => setPythonCode(e.target.value)}
                  className="w-full h-60 bg-neutral-950 border border-neutral-800 rounded-xl p-3 font-mono text-xs text-emerald-400 focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="bg-neutral-950 border border-neutral-800 rounded-2xl p-4">
                <h3 className="text-xs font-bold text-neutral-500 uppercase tracking-wider mb-2 border-b border-neutral-800 pb-2">Terminal Çıktısı (Stdout)</h3>
                <pre className="font-mono text-xs text-neutral-300 whitespace-pre-wrap leading-relaxed max-h-48 overflow-y-auto">
                  {pythonOutput}
                </pre>
              </div>
            </div>
          )}

        </div>
      </div>

      {/* SETTINGS MODAL */}
      {isSettingsOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-neutral-900 border border-neutral-800 rounded-2xl max-w-md w-full p-6 relative animate-in fade-in-50 zoom-in-95 duration-200">
            <button 
              onClick={() => setIsSettingsOpen(false)}
              className="absolute top-4 right-4 text-neutral-400 hover:text-white transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
            <div className="flex items-center gap-2 mb-4 border-b border-neutral-800 pb-3">
              <Sparkles className="w-5 h-5 text-purple-400" />
              <h2 className="text-lg font-bold text-white">Bağlantı & LLM Ayarları</h2>
            </div>
            
            <p className="text-xs text-neutral-400 mb-4 leading-relaxed">
              Buradaki API anahtarları tarayıcınızda (localStorage) saklanır ve doğrudan backend AI route'umuza custom header olarak gönderilir.
            </p>

            <form onSubmit={(e) => {
              e.preventDefault()
              const fd = new FormData(e.currentTarget)
              const selectedProvider = fd.get('provider') as string
              let selectedModel = fd.get('model_select') as string
              if (selectedModel === 'custom') {
                selectedModel = fd.get('model_custom') as string
              }
              saveSettings(
                fd.get('apiKey') as string,
                selectedProvider,
                selectedModel
              )
            }} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-neutral-400">Yapay Zeka Sağlayıcısı</label>
                <select 
                  name="provider" 
                  value={provider} 
                  onChange={(e) => {
                    const nextProv = e.target.value
                    setProvider(nextProv)
                    // Set a default popular model for the selected provider
                    if (nextProv === 'openai') setCustomModel('gpt-4.1-mini')
                    else if (nextProv === 'deepseek') setCustomModel('deepseek-v4-flash')
                    else if (nextProv === 'groq') setCustomModel('llama-3.3-70b-versatile')
                    else if (nextProv === 'openrouter') setCustomModel('meta-llama/llama-3.3-70b-instruct:free')
                    else if (nextProv === 'anthropic') setCustomModel('claude-sonnet-4-6')
                    else if (nextProv === 'gemini') setCustomModel('gemini-3.5-flash')
                  }}
                  className="bg-neutral-950 border border-neutral-800 rounded-xl px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-purple-500"
                >
                  <option value="openai">OpenAI</option>
                  <option value="deepseek">DeepSeek</option>
                  <option value="groq">Groq</option>
                  <option value="openrouter">OpenRouter</option>
                  <option value="anthropic">Anthropic (Claude)</option>
                  <option value="gemini">Google Gemini</option>
                </select>
              </div>

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-neutral-400">Model Seçimi</label>
                <select 
                  name="model_select" 
                  value={
                    // If current customModel is not in the predefined lists, set select to 'custom'
                    (provider === 'openai' && ['gpt-4.1-mini', 'gpt-4.1', 'gpt-4o-mini', 'gpt-4o', 'o4-mini', 'o3'].includes(customModel)) ||
                    (provider === 'deepseek' && ['deepseek-v4-flash', 'deepseek-v4-pro', 'deepseek-chat', 'deepseek-reasoner'].includes(customModel)) ||
                    (provider === 'groq' && ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'llama3-70b-8192'].includes(customModel)) ||
                    (provider === 'openrouter' && ['meta-llama/llama-3.3-70b-instruct:free', 'google/gemma-4-31b-it:free', 'deepseek/deepseek-chat', 'openai/gpt-4o-mini'].includes(customModel)) ||
                    (provider === 'anthropic' && ['claude-sonnet-4-6', 'claude-opus-4-6', 'claude-haiku-4-5', 'claude-sonnet-4-5', 'claude-opus-4-5'].includes(customModel)) ||
                    (provider === 'gemini' && ['gemini-3.5-flash', 'gemini-2.5-flash', 'gemini-2.5-pro'].includes(customModel))
                      ? customModel : 'custom'
                  }
                  onChange={(e) => {
                    if (e.target.value !== 'custom') {
                      setCustomModel(e.target.value)
                    }
                  }}
                  className="bg-neutral-950 border border-neutral-800 rounded-xl px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-purple-500"
                >
                  {provider === 'openai' && (
                    <>
                      <option value="gpt-4.1-mini">gpt-4.1-mini (Hızlı & Ekonomik - Önerilen)</option>
                      <option value="gpt-4.1">gpt-4.1 (Dengeli)</option>
                      <option value="gpt-4o-mini">gpt-4o-mini (Ekonomik)</option>
                      <option value="gpt-4o">gpt-4o (Çok Yönlü)</option>
                      <option value="o4-mini">o4-mini (Akıl Yürütme - Ekonomik)</option>
                      <option value="o3">o3 (Akıl Yürütme - Güçlü)</option>
                    </>
                  )}
                  {provider === 'deepseek' && (
                    <>
                      <option value="deepseek-v4-flash">deepseek-v4-flash (V4 Flash - Önerilen)</option>
                      <option value="deepseek-v4-pro">deepseek-v4-pro (V4 Pro)</option>
                      <option value="deepseek-chat">deepseek-chat (V3 Legacy)</option>
                      <option value="deepseek-reasoner">deepseek-reasoner (R1 Düşünsel Legacy)</option>
                    </>
                  )}
                  {provider === 'groq' && (
                    <>
                      <option value="llama-3.3-70b-versatile">llama-3.3-70b-versatile (Önerilen)</option>
                      <option value="llama-3.1-8b-instant">llama-3.1-8b-instant (Çok Hızlı)</option>
                      <option value="llama3-70b-8192">llama3-70b-8192 (Legacy)</option>
                    </>
                  )}
                  {provider === 'openrouter' && (
                    <>
                      <option value="meta-llama/llama-3.3-70b-instruct:free">llama-3.3-70b:free (Ücretsiz - Önerilen)</option>
                      <option value="google/gemma-4-31b-it:free">gemma-4-31b:free (Ücretsiz)</option>
                      <option value="deepseek/deepseek-chat">deepseek-chat (Ücretli)</option>
                      <option value="openai/gpt-4o-mini">gpt-4o-mini (Ücretli)</option>
                    </>
                  )}
                  {provider === 'anthropic' && (
                    <>
                      <option value="claude-sonnet-4-6">claude-sonnet-4-6 (Sonnet - Önerilen)</option>
                      <option value="claude-opus-4-6">claude-opus-4-6 (Opus - Güçlü Ajan)</option>
                      <option value="claude-haiku-4-5">claude-haiku-4-5 (Haiku - Hızlı)</option>
                      <option value="claude-sonnet-4-5">claude-sonnet-4-5 (Sonnet 4.5)</option>
                      <option value="claude-opus-4-5">claude-opus-4-5 (Opus 4.5 - Premium)</option>
                    </>
                  )}
                  {provider === 'gemini' && (
                    <>
                      <option value="gemini-3.5-flash">gemini-3.5-flash (En Yeni Flash - Önerilen)</option>
                      <option value="gemini-2.5-flash">gemini-2.5-flash (Kararlı Flash)</option>
                      <option value="gemini-2.5-pro">gemini-2.5-pro (Kararlı Pro)</option>
                    </>
                  )}
                  <option value="custom">Özel Model Gir (Manuel)</option>
                </select>
              </div>

              {/* Show manual input if custom is selected or if model is custom */}
              {(!['gpt-4.1-mini', 'gpt-4.1', 'gpt-4o-mini', 'gpt-4o', 'o4-mini', 'o3',
                 'deepseek-chat', 'deepseek-reasoner', 'deepseek-v4-flash', 'deepseek-v4-pro',
                 'llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'llama3-70b-8192',
                 'meta-llama/llama-3.3-70b-instruct:free', 'google/gemma-4-31b-it:free', 'deepseek/deepseek-chat', 'openai/gpt-4o-mini',
                 'claude-sonnet-4-6', 'claude-opus-4-6', 'claude-haiku-4-5', 'claude-sonnet-4-5', 'claude-opus-4-5',
                 'gemini-3.5-flash', 'gemini-2.5-flash', 'gemini-2.5-pro'].includes(customModel)) && (
                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-semibold text-neutral-400">Özel Model Adı</label>
                  <input 
                    type="text" 
                    name="model_custom" 
                    value={customModel} 
                    onChange={(e) => setCustomModel(e.target.value)}
                    placeholder="Örn: deepseek/deepseek-r1"
                    className="bg-neutral-950 border border-neutral-800 rounded-xl px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-purple-500 font-mono"
                  />
                </div>
              )}

              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-semibold text-neutral-400">Kişisel API Anahtarınız (API Key)</label>
                <input 
                  type="password" 
                  name="apiKey" 
                  value={apiKey} 
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                  className="bg-neutral-950 border border-neutral-800 rounded-xl px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-purple-500 font-mono"
                />
              </div>

              <div className="flex justify-end gap-3 mt-2 border-t border-neutral-800 pt-4">
                <button 
                  type="button" 
                  onClick={() => setIsSettingsOpen(false)}
                  className="px-4 py-2 border border-neutral-800 rounded-xl text-xs font-semibold hover:bg-neutral-800 transition-colors"
                >
                  İptal
                </button>
                <button 
                  type="submit" 
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-semibold transition-colors"
                >
                  Kaydet
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  )
}

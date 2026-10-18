import { defineConfig } from 'vitepress'

export default defineConfig({
  base: '/spotlift/',
  title: "SpotLift",
  description: "Python-native Econometric Linear TV Attribution Engine across GA4 and Amazon AMC",
  head: [
    ['script', { type: 'application/ld+json' }, JSON.stringify({
      "@context": "https://schema.org",
      "@type": "SoftwareApplication",
      "name": "SpotLift",
      "applicationCategory": "DeveloperApplication",
      "operatingSystem": "Linux, macOS, Windows",
      "description": "Python-native econometric library for minute-by-minute Linear TV attribution across Google Analytics 4 and Amazon Marketing Cloud (AMC).",
      "installUrl": "https://github.com/flovv/spotlift",
      "offers": {
        "@type": "Offer",
        "price": "0.00",
        "priceCurrency": "EUR"
      }
    })]
  ],
  themeConfig: {
    nav: [
      { text: 'Guide', link: '/index' },
      { text: 'vs. Legacy SaaS', link: '/vs-tvsquared' },
      { text: 'LLMs Index', link: '/llms.txt' },
      { text: 'GitHub', link: 'https://github.com/flovv/spotlift' }
    ],
    sidebar: [
      {
        text: 'Overview',
        items: [
          { text: 'Introduction', link: '/index' },
          { text: 'vs. Legacy Attribution SaaS', link: '/vs-tvsquared' },
        ]
      }
    ]
  }
})

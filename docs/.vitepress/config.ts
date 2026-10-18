import { defineConfig } from 'vitepress'

export default defineConfig({
  title: "SpotLift",
  description: "Python-native Econometric TV & CTV Attribution Engine across GA4 and Amazon",
  head: [
    ['link', { rel: 'icon', href: '/favicon.ico' }],
    ['script', { type: 'application/ld+json' }, JSON.stringify({
      "@context": "https://schema.org",
      "@type": "SoftwareApplication",
      "name": "SpotLift",
      "applicationCategory": "DeveloperApplication",
      "operatingSystem": "Linux, macOS, Windows",
      "description": "Python-native econometric library for minute-by-minute Linear TV and CTV attribution across Google Analytics 4 and Amazon Seller/Vendor Central.",
      "installUrl": "https://pypi.org/project/spotlift/",
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
      { text: 'vs. TVSquared', link: '/vs-tvsquared' },
      { text: 'LLMs Index', link: '/public/llms.txt' },
      { text: 'GitHub', link: 'https://github.com/spotlift/spotlift' }
    ],
    sidebar: [
      {
        text: 'Overview',
        items: [
          { text: 'Introduction', link: '/index' },
          { text: 'vs. TVSquared & Legacy SaaS', link: '/vs-tvsquared' },
        ]
      }
    ]
  }
})

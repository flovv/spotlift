import { defineConfig } from 'vitepress'

export default defineConfig({
  base: '/spotlift/',
  title: "SpotLift",
  description: "Python-Native Econometric Linear TV Attribution Engine across GA4 and Amazon AMC",
  markdown: {
    math: true
  },
  head: [
    ['link', { rel: 'icon', href: '/spotlift/favicon.ico' }],
    ['meta', { name: 'theme-color', content: '#2563eb' }],
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
    siteTitle: 'SpotLift',
    search: {
      provider: 'local'
    },
    nav: [
      { text: 'Quickstart', link: '/quickstart' },
      { text: 'Use Cases', link: '/use-cases/' },
      { text: 'Methodology', link: '/methodology' },
      { text: 'Integrations', items: [
        { text: 'GA4 & BigQuery SQL', link: '/ga4-bigquery' },
        { text: 'Conversion-Rate Bridge', link: '/conversion-rate-bridge' },
        { text: 'Amazon AMC (Pro)', link: '/amazon-amc' },
      ]},
      { text: 'SpotLift Pro', link: '/pro' },
      { text: 'CLI', link: '/cli' },
      { text: 'API Reference', link: '/api-reference' },
      { text: 'vs. Legacy SaaS', link: '/vs-tvsquared' },
      { text: 'GitHub', link: 'https://github.com/flovv/spotlift' }
    ],
    sidebar: [
      {
        text: 'Getting Started',
        items: [
          { text: 'Overview & Philosophy', link: '/index' },
          { text: '5-Minute Quickstart', link: '/quickstart' },
          { text: 'CLI Commands & Demo', link: '/cli' },
        ]
      },
      {
        text: 'Real-World Use Cases',
        items: [
          { text: 'Solutions Overview', link: '/use-cases/' },
          { text: 'Executive Decision Playbook', link: '/use-cases/client-decision-playbook' },
          { text: 'Performance Agency Post-Buy Audit', link: '/use-cases/agency-postbuy-audit' },
          { text: 'DTC E-Commerce Multi-Stage Funnel', link: '/use-cases/dtc-ecommerce-funnel' },
          { text: 'Amazon Retail Halo & Clean Room', link: '/use-cases/amazon-retail-halo' },
          { text: 'Regional Spot TV & Geo-Holdouts', link: '/use-cases/regional-spot-tv-holdouts' },
        ]
      },
      {
        text: 'Econometric Methodology',
        items: [
          { text: 'Core Econometrics & Baseline', link: '/methodology' },
          { text: 'Conversion-Rate Bridge', link: '/conversion-rate-bridge' },
          { text: 'vs. Legacy Providers & SaaS', link: '/vs-tvsquared' },
        ]
      },
      {
        text: 'Telemetry Integrations',
        items: [
          { text: 'Google Analytics 4 & BigQuery', link: '/ga4-bigquery' },
          { text: 'Amazon AMC & Retail Halo (Pro)', link: '/amazon-amc' },
        ]
      },
      {
        text: 'Enterprise & Pro',
        items: [
          { text: 'SpotLift Pro Engine', link: '/pro' },
          { text: 'Python API Reference', link: '/api-reference' },
        ]
      }
    ],
    socialLinks: [
      { icon: 'github', link: 'https://github.com/flovv/spotlift' }
    ],
    footer: {
      message: 'Released under the MIT License.',
      copyright: 'Copyright © 2026 SpotLift Contributors'
    }
  }
})

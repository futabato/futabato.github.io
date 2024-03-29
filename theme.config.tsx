import React from 'react'
import { DocsThemeConfig } from 'nextra-theme-docs'

const config: DocsThemeConfig = {
  logo: <span>futabato.github.io</span>,
  project: {
    link: 'https://github.com/futabato',
  },
  docsRepositoryBase: 'https://github.com/futabato/futabato.github.io',
  search: {placeholder: 'search'},
  editLink: { component: undefined},
  feedback: {content: undefined},
}

export default config

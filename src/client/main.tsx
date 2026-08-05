import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import 'antd/dist/reset.css'
import './index.css'
import ThemedApp from './components/theme/ThemedApp'
import { ThemeProvider } from './providers/ThemeProvider'
import { installFrontendErrorReporter } from './lib/frontendErrorReporter'

installFrontendErrorReporter()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <ThemedApp />
    </ThemeProvider>
  </StrictMode>,
)

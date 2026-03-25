import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { App } from './App'

describe('App shell', () => {
  it('shows run launch controls', () => {
    render(<App />)
    expect(screen.getByText('Run Launch and Setup')).toBeTruthy()
    expect(screen.getByText('Start run')).toBeTruthy()
  })
})

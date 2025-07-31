import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import { ErrorMessage, getErrorType } from '../ErrorMessage'

describe('ErrorMessage', () => {
  it('renders generic error message by default', () => {
    render(<ErrorMessage />)

    expect(screen.getByText('An unexpected error occurred. Please try again.')).toBeInTheDocument()
  })

  it('renders custom message when provided', () => {
    render(<ErrorMessage message="Custom error message" />)

    expect(screen.getByText('Custom error message')).toBeInTheDocument()
  })

  it('renders retry button when onRetry is provided', () => {
    const onRetry = jest.fn()
    render(<ErrorMessage onRetry={onRetry} />)

    const retryButton = screen.getByRole('button', { name: 'Try again' })
    expect(retryButton).toBeInTheDocument()

    fireEvent.click(retryButton)
    expect(onRetry).toHaveBeenCalled()
  })

  it('does not render retry button when onRetry is not provided', () => {
    render(<ErrorMessage />)

    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })

  it('renders details when provided', () => {
    render(<ErrorMessage details="Additional error details" />)

    expect(screen.getByText('Additional error details')).toBeInTheDocument()
  })

  describe('error types', () => {
    it('renders network error correctly', () => {
      render(<ErrorMessage type="network" />)

      expect(screen.getByText('Network connection failed. Please check your internet connection and try again.')).toBeInTheDocument()
    })

    it('renders server error correctly', () => {
      render(<ErrorMessage type="server" />)

      expect(screen.getByText('Server error occurred. Our team has been notified. Please try again later.')).toBeInTheDocument()
    })

    it('renders not-found error correctly', () => {
      render(<ErrorMessage type="not-found" />)

      expect(screen.getByText('The requested content could not be found.')).toBeInTheDocument()
    })

    it('renders unauthorized error correctly', () => {
      render(<ErrorMessage type="unauthorized" />)

      expect(screen.getByText('You are not authorized to access this content. Please log in and try again.')).toBeInTheDocument()
    })

    it('renders rate-limit error correctly', () => {
      render(<ErrorMessage type="rate-limit" />)

      expect(screen.getByText('Too many requests. Please wait a moment before trying again.')).toBeInTheDocument()
    })

    it('renders validation error correctly', () => {
      render(<ErrorMessage type="validation" />)

      expect(screen.getByText('Invalid input provided. Please check your data and try again.')).toBeInTheDocument()
    })
  })
})

describe('getErrorType', () => {
  it('returns generic for null/undefined error', () => {
    expect(getErrorType(null)).toBe('generic')
    expect(getErrorType(undefined)).toBe('generic')
  })

  it('returns network for network-related errors', () => {
    const networkError = { message: 'fetch failed' }
    expect(getErrorType(networkError)).toBe('network')

    const networkError2 = { message: 'network error' }
    expect(getErrorType(networkError2)).toBe('network')
  })

  it('returns correct type based on status code', () => {
    expect(getErrorType({ status: 401 })).toBe('unauthorized')
    expect(getErrorType({ status: 403 })).toBe('unauthorized')
    expect(getErrorType({ status: 404 })).toBe('not-found')
    expect(getErrorType({ status: 429 })).toBe('rate-limit')
    expect(getErrorType({ status: 400 })).toBe('validation')
    expect(getErrorType({ status: 422 })).toBe('validation')
    expect(getErrorType({ status: 500 })).toBe('server')
    expect(getErrorType({ status: 502 })).toBe('server')
  })

  it('returns correct type based on response.status', () => {
    expect(getErrorType({ response: { status: 401 } })).toBe('unauthorized')
    expect(getErrorType({ response: { status: 500 } })).toBe('server')
  })

  it('returns generic for unknown status codes', () => {
    expect(getErrorType({ status: 200 })).toBe('generic')
    expect(getErrorType({ status: 300 })).toBe('generic')
  })
})
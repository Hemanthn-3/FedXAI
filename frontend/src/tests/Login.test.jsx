
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { Login } from '../pages/Login';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

// Mock context and router hooks
vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}));

vi.mock('react-router-dom', () => ({
  useNavigate: vi.fn(),
}));

// Mock lucide icons
vi.mock('lucide-react', () => ({
  Activity: () => <div data-testid="activity-icon" />,
  Lock: () => <div data-testid="lock-icon" />,
  Mail: () => <div data-testid="mail-icon" />,
  AlertCircle: () => <div data-testid="alert-icon" />,
}));

describe('Login Component', () => {
  let mockLogin;
  let mockNavigate;

  beforeEach(() => {
    vi.clearAllMocks();
    mockLogin = vi.fn();
    mockNavigate = vi.fn();
    useAuth.mockReturnValue({ login: mockLogin });
    useNavigate.mockReturnValue(mockNavigate);
  });

  it('renders form inputs and submit button correctly', () => {
    render(<Login />);
    
    expect(screen.getByPlaceholderText('Email Address')).toBeDefined();
    expect(screen.getByPlaceholderText('Password')).toBeDefined();
    expect(screen.getByRole('button', { name: 'Sign In' })).toBeDefined();
  });

  it('updates input values when typing', () => {
    render(<Login />);
    
    const emailInput = screen.getByPlaceholderText('Email Address');
    const passwordInput = screen.getByPlaceholderText('Password');

    fireEvent.change(emailInput, { target: { value: 'doctor@test.com' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });

    expect(emailInput.value).toBe('doctor@test.com');
    expect(passwordInput.value).toBe('password123');
  });

  it('calls login and navigates to "/" on successful submit', async () => {
    mockLogin.mockResolvedValueOnce();
    render(<Login />);
    
    const emailInput = screen.getByPlaceholderText('Email Address');
    const passwordInput = screen.getByPlaceholderText('Password');
    const submitButton = screen.getByRole('button', { name: 'Sign In' });

    fireEvent.change(emailInput, { target: { value: 'doctor@test.com' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });
    fireEvent.click(submitButton);

    expect(mockLogin).toHaveBeenCalledWith('doctor@test.com', 'password123');
    
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/');
    });
  });

  it('displays error message on failed login attempt', async () => {
    mockLogin.mockRejectedValueOnce(new Error('Invalid email or password'));
    render(<Login />);
    
    const emailInput = screen.getByPlaceholderText('Email Address');
    const passwordInput = screen.getByPlaceholderText('Password');
    const submitButton = screen.getByRole('button', { name: 'Sign In' });

    fireEvent.change(emailInput, { target: { value: 'doctor@test.com' } });
    fireEvent.change(passwordInput, { target: { value: 'wrong_pwd' } });
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(screen.getByText('Invalid email or password')).toBeDefined();
    });
  });
});

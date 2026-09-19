import { render, screen } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { ProtectedRoute } from '../components/ProtectedRoute';
import { useAuth } from '../context/AuthContext';

// Mock context and router elements
vi.mock('../context/AuthContext', () => ({
  useAuth: vi.fn(),
}));

vi.mock('react-router-dom', () => ({
  Navigate: vi.fn(({ to }) => <div data-testid="navigate" data-to={to} />),
}));

describe('ProtectedRoute Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('redirects to "/login" if user is not authenticated', () => {
    useAuth.mockReturnValue({ user: null });
    
    render(
      <ProtectedRoute>
        <div data-testid="child">Protected Content</div>
      </ProtectedRoute>
    );

    expect(screen.queryByTestId('child')).toBeNull();
    const navigateEl = screen.getByTestId('navigate');
    expect(navigateEl).toBeDefined();
    expect(navigateEl.getAttribute('data-to')).toBe('/login');
  });

  it('renders children if user is authenticated and no role is required', () => {
    useAuth.mockReturnValue({ user: { id: '1', role: 'doctor' } });

    render(
      <ProtectedRoute>
        <div data-testid="child">Protected Content</div>
      </ProtectedRoute>
    );

    expect(screen.getByTestId('child')).toBeDefined();
    expect(screen.getByText('Protected Content')).toBeDefined();
    expect(screen.queryByTestId('navigate')).toBeNull();
  });

  it('renders children if user has the exact required role', () => {
    useAuth.mockReturnValue({ user: { id: '1', role: 'doctor' } });

    render(
      <ProtectedRoute requiredRole="doctor">
        <div data-testid="child">Doctor View</div>
      </ProtectedRoute>
    );

    expect(screen.getByTestId('child')).toBeDefined();
    expect(screen.queryByTestId('navigate')).toBeNull();
  });

  it('renders children if user is system_admin regardless of requiredRole', () => {
    useAuth.mockReturnValue({ user: { id: '1', role: 'system_admin' } });

    render(
      <ProtectedRoute requiredRole="doctor">
        <div data-testid="child">Doctor View</div>
      </ProtectedRoute>
    );

    expect(screen.getByTestId('child')).toBeDefined();
    expect(screen.queryByTestId('navigate')).toBeNull();
  });

  it('redirects to "/" if user does not have the required role and is not system_admin', () => {
    useAuth.mockReturnValue({ user: { id: '1', role: 'researcher' } });

    render(
      <ProtectedRoute requiredRole="doctor">
        <div data-testid="child">Doctor View</div>
      </ProtectedRoute>
    );

    expect(screen.queryByTestId('child')).toBeNull();
    const navigateEl = screen.getByTestId('navigate');
    expect(navigateEl).toBeDefined();
    expect(navigateEl.getAttribute('data-to')).toBe('/');
  });
});

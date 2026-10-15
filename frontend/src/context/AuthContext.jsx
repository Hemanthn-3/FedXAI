import { createContext, useContext, useState, useEffect } from 'react';
import { authApi } from '../api';

const AuthContext = createContext(null);

export const resolveHospitalNode = (val) => {
  if (!val) return 'Hospital Node 1';
  const str = String(val).toLowerCase();
  if (str.includes('all')) {
    return 'All Hospital Nodes';
  }
  if (str.includes('node 2') || str.includes('node_2') || str.includes('hospital_2') || str.includes('.h2') || str.includes('h2@')) {
    return 'Hospital Node 2';
  }
  if (str.includes('node 3') || str.includes('node_3') || str.includes('hospital_3') || str.includes('.h3') || str.includes('h3@')) {
    return 'Hospital Node 3';
  }
  return 'Hospital Node 1';
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeNode, setActiveNodeState] = useState(() => {
    return resolveHospitalNode(localStorage.getItem('active_hospital_node'));
  });

  const setActiveNode = (nodeName) => {
    const resolved = resolveHospitalNode(nodeName);
    localStorage.setItem('active_hospital_node', resolved);
    setActiveNodeState(resolved);
  };

  const applyUserNode = (userData) => {
    if (!userData) return;
    if (userData.role === 'system_admin') {
      const stored = localStorage.getItem('active_hospital_node');
      if (stored) {
        setActiveNodeState(stored);
      } else {
        setActiveNodeState('All Hospital Nodes');
      }
    } else {
      const nodeName = userData.hospital_name || resolveHospitalNode(userData.email);
      setActiveNode(nodeName);
    }
  };

  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('access_token');
      if (token) {
        try {
          const { data } = await authApi.me();
          setUser(data);
          applyUserNode(data);
        } catch {
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
          setUser(null);
        }
      }
      setLoading(false);
    };
    checkAuth();
  }, []);

  const login = async (email, password) => {
    const { data } = await authApi.login({ email, password });
    localStorage.setItem('access_token', data.access_token);
    if (data.refresh_token) {
      localStorage.setItem('refresh_token', data.refresh_token);
    }
    const { data: userData } = await authApi.me();
    setUser(userData);
    applyUserNode(userData);
    return userData;
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('active_hospital_node');
    setUser(null);
    setActiveNodeState('Hospital Node 1');
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, loading, activeNode, setActiveNode }}>
      {!loading && children}
    </AuthContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useAuth = () => useContext(AuthContext) || {};


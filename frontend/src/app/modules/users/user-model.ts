export interface RoleI {
  id: number;
  name: string;
  slug?: string;
  description?: string;
}

export interface UserI {
  id?: number;
  username: string;
  password?: string;
  first_name: string;
  last_name: string;
  email: string;
  job_title?: string;
  avatar?: string; // URL o base64
  role?: RoleI | null;
  roles?: RoleI[];
  status?: 'ACTIVE' | 'INACTIVE';
  is_active?: boolean;
  is_staff?: boolean;
}

import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { UserI } from '../modules/users/user-model';

@Injectable({ providedIn: 'root' })
export class UserService {
  private apiUrl = 'http://127.0.0.1:8000/api/users/';

  constructor(private http: HttpClient) {}

  getUsers(): Observable<UserI[]> {
    return this.http.get<UserI[]>(this.apiUrl, { withCredentials: true });
  }

  deleteUser(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}${id}/`, { withCredentials: true });
  }
}

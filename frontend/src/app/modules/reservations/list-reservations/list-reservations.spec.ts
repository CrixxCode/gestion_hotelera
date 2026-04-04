import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of } from 'rxjs';

import { ListReservations } from './list-reservations';
import { ReservationService } from '../../../services/reservation';
import { MasterDataService } from '../../../services/master-data.service';
import { ClientsService } from '../../../services/client';
import { RoomService } from '../../../services/room';

describe('ListReservations', () => {
  let component: ListReservations;
  let fixture: ComponentFixture<ListReservations>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ListReservations],
      providers: [
        {
          provide: ReservationService,
          useValue: {
            listReservations: () => of([]),
            listReservationPolicies: () => of([]),
            getReservationById: () =>
              of({
                id: 1,
                client: 1,
                status: 1,
                origin: 1,
                expected_check_in: '2026-03-01',
                expected_check_out: '2026-03-03',
                total_discount: 0,
                rooms_detail: [],
                guests: [],
                deposits: []
              }),
            deleteReservation: () => of(null)
          }
        },
        {
          provide: MasterDataService,
          useValue: {
            listMasterData: () => of([])
          }
        },
        {
          provide: ClientsService,
          useValue: {
            listClients: () => of([])
          }
        },
        {
          provide: RoomService,
          useValue: {
            listRooms: () => of([])
          }
        }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(ListReservations);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
